"""
PhilIRI preprocessing: schema harmonization and silver layer writing.

Handles two key-stages (KS2 = Elementary G4-G6, KS3 = Secondary G7-G10)
across two periods (BoSY, EoSY) and two school years (2024-25, 2025-26).

Column naming inconsistency across source files:
- KS2 BoSY uses:  {G} {X}LD {lang} {level}   e.g. "G4 2LD Fil Frustration"
- KS3 BoSY uses:  {G} {lang} {level} {X}Level  e.g. "G7 Fil Frustration 2Level"
Normalization target: KS2 format — {G} {X}LD {lang} {level}.

Data quality issues handled:
- Duplicate column G5 3LD Fil Frustration (appears twice in KS2 2024-25 BoSY).
- KS3 EoSY 2024-25 "Total Enrolled (G4-G6)" label should be (G7-G10).
- Non-breaking spaces (U+00A0) in filenames (handled upstream via glob).
- BOM character (U+FEFF) stripped from first column on load.
"""

import glob
import pathlib
import re

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHILIRI_BRONZE_DIR = "data/bronze/philiri"
PHILIRI_SILVER_DIR = "data/silver/philiri"

METADATA_COLUMNS = ["Region", "Division", "District", "School Name"]

KS2_GRADES = ["G4", "G5", "G6"]
KS3_GRADES = ["G7", "G8", "G9", "G10"]
LANGUAGES = ["Fil", "Eng"]

# BoSY levels per language: Grade Ready + 2LD (F/I/Ind) + 3LD (F/I/Ind)
BOSY_LEVELS_PER_LANG = [
    "Grade Ready",
    "2LD Frustration",
    "2LD Instructional",
    "2LD Independent",
    "3LD Frustration",
    "3LD Instructional",
    "3LD Independent",
]

# EoSY levels per language
EOSY_LEVELS_PER_LANG = ["Frustration", "Instructional", "Independent"]


def _bosy_columns(grades, per_lang_assessed=False):
    """Canonical BoSY column names for the given grade list.

    Parameters
    ----------
    per_lang_assessed : bool
        If True, generates ``{G} {lang} Assessed`` (KS3 BoSY format).
        If False, generates a single ``{G} Assessed`` per grade (KS2 BoSY format).
    """
    cols = []
    for g in grades:
        if not per_lang_assessed:
            cols.append(f"{g} Assessed")
        for lang in LANGUAGES:
            if per_lang_assessed:
                cols.append(f"{g} {lang} Assessed")
            for level in BOSY_LEVELS_PER_LANG:
                if level == "Grade Ready":
                    cols.append(f"{g} {lang} Grade Ready")
                else:
                    xld, severity = level.split(" ", 1)
                    cols.append(f"{g} {xld} {lang} {severity}")
    return cols


def _eosy_columns_ks2(grades):
    """Canonical EoSY KS2 column names (one Assessed per grade)."""
    cols = []
    for g in grades:
        cols.append(f"{g} Assessed")
        for lang in LANGUAGES:
            for level in EOSY_LEVELS_PER_LANG:
                cols.append(f"{g} {lang} {level}")
    return cols


def _eosy_columns_ks3(grades, per_lang_assessed=True):
    """Canonical EoSY KS3 column names.

    2025-26 has Assessed per grade-language; 2024-25 has one Assessed per grade.
    """
    cols = []
    for g in grades:
        if not per_lang_assessed:
            cols.append(f"{g} Assessed")
        for lang in LANGUAGES:
            if per_lang_assessed:
                cols.append(f"{g} {lang} Assessed")
            for level in EOSY_LEVELS_PER_LANG:
                cols.append(f"{g} {lang} {level}")
    return cols


KS2_BOSY_COLUMNS = _bosy_columns(KS2_GRADES, per_lang_assessed=False)
KS3_BOSY_COLUMNS = _bosy_columns(KS3_GRADES, per_lang_assessed=True)
KS2_EOSY_COLUMNS = _eosy_columns_ks2(KS2_GRADES)
KS3_EOSY_COLUMNS_PER_GRADE = _eosy_columns_ks3(KS3_GRADES, per_lang_assessed=False)
KS3_EOSY_COLUMNS_PER_LANG = _eosy_columns_ks3(KS3_GRADES, per_lang_assessed=True)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

# Filename pattern: one file per (ks, sy, period).
# Files use non-breaking spaces (U+00A0) — always use glob to discover.
_BRONZE_FILE_HINTS = {
    ("ks2", "2024-25", "BoSY"): "*Elementary*BoSY*",
    ("ks2", "2024-25", "EoSY"): "*Elementary*EoSY*",
    ("ks2", "2025-26", "BoSY"): "*KS2*BoSY*",
    ("ks2", "2025-26", "EoSY"): "*KS2*EoSY*",
    ("ks3", "2024-25", "BoSY"): "*Secondary*BoSY*",
    ("ks3", "2024-25", "EoSY"): "*Secondary*EoSY*",
    ("ks3", "2025-26", "BoSY"): "*KS3*BoSY*",
    ("ks3", "2025-26", "EoSY"): "*KS3*EoSY*",
}


def resolve_philiri_files(bronze_dir=None):
    """
    Scan the bronze PhilIRI directory and return a file map.

    Returns
    -------
    dict
        ``{(ks, school_year, period): path}`` for each file found.
        ``ks`` is ``'ks2'`` or ``'ks3'``.
    """
    if bronze_dir is None:
        bronze_dir = PHILIRI_BRONZE_DIR

    result = {}
    for key, pattern in _BRONZE_FILE_HINTS.items():
        matches = glob.glob(str(pathlib.Path(bronze_dir) / pattern))
        if matches:
            result[key] = matches[0]
        else:
            print(f"  ⚠ No file found for {key} (pattern: {pattern})")

    return result


# ---------------------------------------------------------------------------
# Column normalization
# ---------------------------------------------------------------------------

def _normalize_philiri_columns(df):
    """
    Normalize column names to the KS2 canonical convention.

    KS3 BoSY uses ``{G} {lang} {level} {X}Level``; this rewrites those
    to ``{G} {X}LD {lang} {level}``.

    Also strips BOM from first column name and strips whitespace.
    """
    def _fix(col):
        col = col.strip().lstrip("﻿")
        # Pattern: "{G} {lang} {level} {X}Level"
        # e.g. "G7 Fil Frustration 2Level" → "G7 2LD Fil Frustration"
        m = re.match(
            r"^(G\d+)\s+(Fil|Eng)\s+(Frustration|Instructional|Independent)\s+(\d)Level$",
            col,
        )
        if m:
            grade, lang, level, n = m.groups()
            return f"{grade} {n}LD {lang} {level}"
        return col

    df = df.copy()
    df.columns = [_fix(c) for c in df.columns]
    return df


def _drop_duplicates_columns(df):
    """Drop duplicate columns (keep first), e.g. G5 3LD Fil Frustration.1."""
    seen = set()
    keep = []
    for col in df.columns:
        # Pandas renames duplicates with .N suffix during read_csv
        base = re.sub(r"\.\d+$", "", col)
        if base not in seen:
            seen.add(base)
            keep.append(col)
    return df[keep].rename(columns=lambda c: re.sub(r"\.\d+$", "", c))


# ---------------------------------------------------------------------------
# Numeric cleaning
# ---------------------------------------------------------------------------

def _clean_numeric_columns(df, keep_cols):
    """
    Convert specified columns to numeric (comma-safe) and fill missing
    canonical columns with NaN.
    """
    df = df.copy()
    for col in keep_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            )
        else:
            df[col] = np.nan
    return df


# ---------------------------------------------------------------------------
# Metadata fixes
# ---------------------------------------------------------------------------

def _fix_ks3_eosy_2024_enrolled_header(df):
    """
    KS3 EoSY 2024-25 has 'Total Enrolled (G4-G6)' as a copy-paste error.
    Rename to 'Total Enrolled (G7-G10)'.
    """
    df = df.copy()
    df.columns = [
        "Total Enrolled (G7-G10)" if c == "Total Enrolled (G4-G6)" else c
        for c in df.columns
    ]
    return df


# ---------------------------------------------------------------------------
# Single-file loader
# ---------------------------------------------------------------------------

def load_philiri_file(path, ks, school_year, period):
    """
    Load a single PhilIRI CSV, normalize column names, clean numerics,
    and return a tidy DataFrame indexed by School ID.

    Parameters
    ----------
    path : str or pathlib.Path
    ks : str
        ``'ks2'`` or ``'ks3'``.
    school_year : str
        e.g. ``'2024-25'``.
    period : str
        ``'BoSY'`` or ``'EoSY'``.

    Returns
    -------
    pandas.DataFrame
        School ID as index; metadata columns; data columns (raw numeric);
        ``school_year``, ``period``, ``ks`` tags.
    """
    df = pd.read_csv(path, low_memory=False)
    df = _normalize_philiri_columns(df)
    df = _drop_duplicates_columns(df)

    # KS3 EoSY 2024-25 enrolled-header fix
    if ks == "ks3" and period == "EoSY" and school_year == "2024-25":
        df = _fix_ks3_eosy_2024_enrolled_header(df)

    # Identify School ID column (strip BOM if present)
    sid_col = next(
        (c for c in df.columns if c.strip().lstrip("﻿") == "School ID"),
        None,
    )
    if sid_col is None:
        raise ValueError(f"School ID column not found in {path}")
    df = df.rename(columns={sid_col: "School ID"})

    # Determine canonical data columns
    if period == "BoSY":
        data_cols = KS2_BOSY_COLUMNS if ks == "ks2" else KS3_BOSY_COLUMNS
    else:  # EoSY
        if ks == "ks2":
            data_cols = KS2_EOSY_COLUMNS
        else:
            # 2025-26 has per-lang Assessed; 2024-25 has per-grade Assessed
            if school_year == "2025-26":
                data_cols = KS3_EOSY_COLUMNS_PER_LANG
            else:
                data_cols = KS3_EOSY_COLUMNS_PER_GRADE

    df = _clean_numeric_columns(df, data_cols)

    # Set School ID as index
    df["School ID"] = pd.to_numeric(df["School ID"], errors="coerce")
    df = df.dropna(subset=["School ID"])
    df["School ID"] = df["School ID"].astype(int)
    df = df.set_index("School ID")

    # Keep metadata and data columns only
    meta_present = [c for c in METADATA_COLUMNS if c in df.columns]
    df = df[meta_present + data_cols]

    df["school_year"] = school_year
    df["period"] = period
    df["ks"] = ks

    return df


# ---------------------------------------------------------------------------
# Silver writer
# ---------------------------------------------------------------------------

def write_silver_philiri(file_map=None, output_dir=None):
    """
    Write harmonized PhilIRI data to the silver layer.

    Produces one parquet per (ks, school_year, period).

    Parameters
    ----------
    file_map : dict, optional
        ``{(ks, school_year, period): path}``.
        Defaults to ``resolve_philiri_files()``.
    output_dir : str, optional
        Destination directory.  Defaults to ``PHILIRI_SILVER_DIR``.
    """
    if file_map is None:
        file_map = resolve_philiri_files()
    if output_dir is None:
        output_dir = PHILIRI_SILVER_DIR

    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    written = []
    for (ks, sy, period), path in sorted(file_map.items()):
        print(f"Loading PhilIRI {ks} {sy} {period} ...")
        df = load_philiri_file(path, ks, sy, period)
        out_path = out / f"{ks}_{sy}_{period}.parquet"
        df.to_parquet(out_path)
        print(f"  → {out_path} ({len(df)} schools)")
        written.append(out_path)

    return written
