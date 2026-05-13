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
    ("ks2", "2024-25", "BoSY"): "*Archive*Elementary*BoSY*",
    ("ks2", "2024-25", "EoSY"): "*Archive*Elementary*EoSY*",
    ("ks2", "2025-26", "BoSY"): "*KS2*BoSY*",
    ("ks2", "2025-26", "EoSY"): "*KS2*EoSY*",
    ("ks3", "2024-25", "BoSY"): "*Archive*Secondary*BoSY*",
    ("ks3", "2024-25", "EoSY"): "*Archive*Secondary*EoSY*",
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


# ---------------------------------------------------------------------------
# Grade-language groups
# ---------------------------------------------------------------------------

PHILIRI_GRADES_BY_KS = {
    "ks2": KS2_GRADES,
    "ks3": KS3_GRADES,
}


def get_philiri_groups(ks):
    """Return ordered list of (grade, lang) tuples for a key stage."""
    return [(g, lang) for g in PHILIRI_GRADES_BY_KS[ks] for lang in LANGUAGES]


# ---------------------------------------------------------------------------
# Raw count helpers (per grade-language group)
# ---------------------------------------------------------------------------

def _philiri_group_counts_bosy(raw_df, grade, lang):
    """
    Return (frustration, instructional, independent) collapsed raw count
    Series for a BoSY grade-language group.

    Collapse:
        Independent  = Grade Ready + 2LD Independent
        Instructional = 2LD Instructional + 3LD Independent
        Frustration  = 2LD Frustration + 3LD Instructional + 3LD Frustration
    """
    def _get(col):
        return (
            raw_df[col].fillna(0) if col in raw_df.columns
            else pd.Series(0.0, index=raw_df.index)
        )

    independent = (
        _get(f"{grade} {lang} Grade Ready")
        + _get(f"{grade} 2LD {lang} Independent")
    )
    instructional = (
        _get(f"{grade} 2LD {lang} Instructional")
        + _get(f"{grade} 3LD {lang} Independent")
    )
    frustration = (
        _get(f"{grade} 2LD {lang} Frustration")
        + _get(f"{grade} 3LD {lang} Instructional")
        + _get(f"{grade} 3LD {lang} Frustration")
    )
    return frustration, instructional, independent


def _philiri_group_counts_eosy(raw_df, grade, lang):
    """
    Return (frustration, instructional, independent) raw count Series for
    an EoSY grade-language group.
    """
    def _get(col):
        return (
            raw_df[col].fillna(0) if col in raw_df.columns
            else pd.Series(0.0, index=raw_df.index)
        )

    return (
        _get(f"{grade} {lang} Frustration"),
        _get(f"{grade} {lang} Instructional"),
        _get(f"{grade} {lang} Independent"),
    )


# ---------------------------------------------------------------------------
# Percentage computation
# ---------------------------------------------------------------------------

def compute_philiri_percentages(raw_df, ks, period):
    """
    Compute 3-level collapsed percentages from a PhilIRI silver DataFrame.

    BoSY collapse:
        Independent  = Grade Ready + 2LD Independent
        Instructional = 2LD Instructional + 3LD Independent
        Frustration  = 2LD Frustration + 3LD Instructional + 3LD Frustration

    EoSY: normalises the three existing EoSY counts directly.

    The denominator is the per-language column sum in all cases (not the
    combined ``{G} Assessed`` column, which is a combined grade total for
    KS2 and therefore unsuitable as a per-language denominator).

    Returns
    -------
    pandas.DataFrame
        Columns: ``{G} {lang} Frustration``, ``{G} {lang} Instructional``,
        ``{G} {lang} Independent`` (0–100 scale).  NaN where denominator
        is zero (no assessed students in that group).
    """
    groups = get_philiri_groups(ks)
    result = {}

    for grade, lang in groups:
        if period == "BoSY":
            frust, inst, indep = _philiri_group_counts_bosy(raw_df, grade, lang)
        else:
            frust, inst, indep = _philiri_group_counts_eosy(raw_df, grade, lang)

        denom = (frust + inst + indep).replace(0, np.nan)
        result[f"{grade} {lang} Frustration"] = frust / denom * 100
        result[f"{grade} {lang} Instructional"] = inst / denom * 100
        result[f"{grade} {lang} Independent"] = indep / denom * 100

    return pd.DataFrame(result, index=raw_df.index)


def compute_philiri_percentages_7level(raw_df, ks):
    """
    Compute 7-level BoSY percentages without collapse.

    Ordinal order (1 = worst → 7 = best):
        1: 3LD Frustration, 2: 3LD Instructional, 3: 3LD Independent,
        4: 2LD Frustration, 5: 2LD Instructional, 6: 2LD Independent,
        7: Grade Ready

    Returns
    -------
    pandas.DataFrame
        Columns: ``{G} {lang} 3LD Frustration`` … ``{G} {lang} Grade Ready``
        (0–100 scale).  NaN where denominator is zero.
    """
    groups = get_philiri_groups(ks)
    level_labels = [
        "3LD Frustration", "3LD Instructional", "3LD Independent",
        "2LD Frustration", "2LD Instructional", "2LD Independent",
        "Grade Ready",
    ]
    result = {}

    for grade, lang in groups:
        raw_cols = [
            f"{grade} 3LD {lang} Frustration",
            f"{grade} 3LD {lang} Instructional",
            f"{grade} 3LD {lang} Independent",
            f"{grade} 2LD {lang} Frustration",
            f"{grade} 2LD {lang} Instructional",
            f"{grade} 2LD {lang} Independent",
            f"{grade} {lang} Grade Ready",
        ]
        counts = [
            raw_df[c].fillna(0) if c in raw_df.columns
            else pd.Series(0.0, index=raw_df.index)
            for c in raw_cols
        ]
        denom = sum(counts).replace(0, np.nan)
        for label, count in zip(level_labels, counts):
            result[f"{grade} {lang} {label}"] = count / denom * 100

    return pd.DataFrame(result, index=raw_df.index)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_philiri(pct3_df, raw_df, ks, period):
    """
    Compute validity flags for a single PhilIRI timepoint.

    ``valid``       — at least one grade-language group has data.
    ``valid_strict`` — all grades present + ≥ 4 groups + ≥ 15 assessed per group.

    Returns
    -------
    pandas.DataFrame
        Columns: ``valid``, ``valid_strict``, ``groups_available``,
        ``min_group_assessed``, ``has_all_grades``.
    """
    grades = PHILIRI_GRADES_BY_KS[ks]
    groups = get_philiri_groups(ks)
    index = pct3_df.index

    groups_available = pd.Series(0, index=index, dtype=int)
    min_assessed = pd.Series(np.inf, index=index, dtype=float)
    grade_has_data = {g: pd.Series(False, index=index) for g in grades}

    for grade, lang in groups:
        cols = [
            f"{grade} {lang} Frustration",
            f"{grade} {lang} Instructional",
            f"{grade} {lang} Independent",
        ]
        if not all(c in pct3_df.columns for c in cols):
            continue
        has_group = pct3_df[cols].notna().all(axis=1)

        # Assessed count = denominator = sum of raw level columns
        if period == "BoSY":
            frust, inst, indep = _philiri_group_counts_bosy(raw_df, grade, lang)
        else:
            frust, inst, indep = _philiri_group_counts_eosy(raw_df, grade, lang)
        assessed = (frust + inst + indep).where(has_group, other=np.nan)

        groups_available += has_group.astype(int)
        min_assessed = pd.concat([min_assessed, assessed], axis=1).min(axis=1)
        grade_has_data[grade] = grade_has_data[grade] | has_group

    min_assessed = min_assessed.replace(np.inf, np.nan)
    has_all_grades = pd.concat(
        list(grade_has_data.values()), axis=1
    ).all(axis=1)

    valid = groups_available > 0
    valid_strict = (
        has_all_grades
        & (groups_available >= 4)
        & (min_assessed >= 15)
    )

    return pd.DataFrame({
        "valid": valid,
        "valid_strict": valid_strict,
        "groups_available": groups_available,
        "min_group_assessed": min_assessed,
        "has_all_grades": has_all_grades,
    })
