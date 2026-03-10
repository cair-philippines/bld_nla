"""
CRLA preprocessing: schema harmonization, file loading, and percentage
conversion.

Normalizes raw CRLA CSVs from different school years into an identical
column schema and converts raw counts to percentages per grade-language
group.
"""

import numpy as np
import pandas as pd

from gcs_utils import get_fs, CSDATA_RAW_DIR, CSDATA_MODIFIED_DIR


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

READING_PROFILES = [
    "Lower Emergent",
    "Higher Emergent",
    "Developing",
    "Transitioning",
    "Grade Level",
]

GRADE_LANGUAGE_GROUPS = [
    ("G1", None),
    ("G2", "MT"),
    ("G2", "Fil"),
    ("G3", "MT"),
    ("G3", "Fil"),
    ("G3", "Eng"),
]

# Registry of known raw files on GCS, keyed by (school_year, period).
CRLA_RAW_FILES = {
    ("2024-25", "BoSY"): (
        f"{CSDATA_RAW_DIR}/CRLA Results Archive_SY 2024-25 "
        "Assessment Results_Table_BoSY.csv"
    ),
    ("2024-25", "EoSY"): (
        f"{CSDATA_RAW_DIR}/CRLA Results Archive_SY 2024-25 "
        "Assessment Results_Table_EoSY.csv"
    ),
    ("2025-26", "BoSY"): (
        f"{CSDATA_RAW_DIR}/CRLA National Dashboard_BoSY 2025-26 "
        "Assessment Results_Table.csv"
    ),
}


# ---------------------------------------------------------------------------
# Schema harmonization
# ---------------------------------------------------------------------------

def _canonical_grade_columns():
    """Return the 30 grade-level reading-profile columns in canonical order."""
    cols = []
    for grade, lang in GRADE_LANGUAGE_GROUPS:
        for profile in READING_PROFILES:
            if lang:
                cols.append(f"{grade} {lang} {profile}")
            else:
                cols.append(f"{grade} {profile}")
    return cols


CANONICAL_GRADE_COLUMNS = _canonical_grade_columns()


def harmonize_columns(df):
    """
    Normalize a raw CRLA DataFrame so that all school years share an
    identical column schema.

    Operations:
    1. Fix the ``FIl`` → ``Fil`` typo present in source data.
    2. Strip leading/trailing whitespace from all string columns.
    3. Fix mojibake: ``¤`` (U+00A4) → ``ñ``, ``Ã±`` → ``ñ``.
    4. Drop grade-level "Total" columns (e.g. ``G1 Total Assessed``,
       ``G2 Total MT Assessed``) that vary between years.
    5. Reorder grade-level columns to a canonical order so that
       positional assumptions are never needed downstream.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame as read from a CRLA CSV.

    Returns
    -------
    pandas.DataFrame
        Cleaned DataFrame.  Non-grade columns are preserved as-is;
        grade-level columns follow ``CANONICAL_GRADE_COLUMNS`` order.
    """
    df = df.copy()

    # 1. Fix typo (capital I in "FIl")
    df.columns = [c.replace("FIl", "Fil") for c in df.columns]

    # 2. Strip whitespace from string columns
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].str.strip()

    # 3. Fix mojibake in string columns
    #    ¤ (U+00A4) is corrupted ñ (seen in "Due¤as" → "Dueñas", "Osme¤a" → "Osmeña")
    #    Ã± is double-encoded ñ (seen in "DoÃ±a" → "Doña")
    for col in str_cols:
        df[col] = df[col].str.replace("Ã±", "ñ", regex=False)
        df[col] = df[col].str.replace("\u00a4", "ñ", regex=False)

    # 4. Separate non-grade and grade columns
    grade_cols = [c for c in df.columns if c.startswith("G")]
    non_grade_cols = [c for c in df.columns if not c.startswith("G")]

    # 4. Drop grade-level Total columns
    grade_cols = [c for c in grade_cols if "total" not in c.lower()]

    # 5. Validate all canonical columns are present
    missing = set(CANONICAL_GRADE_COLUMNS) - set(grade_cols)
    if missing:
        raise ValueError(
            f"After harmonization, expected columns are missing: {missing}"
        )

    unexpected = set(grade_cols) - set(CANONICAL_GRADE_COLUMNS)
    if unexpected:
        raise ValueError(
            f"Unexpected grade columns remain after filtering: {unexpected}"
        )

    # 6. Reorder: non-grade columns first, then canonical grade order
    return df[non_grade_cols + CANONICAL_GRADE_COLUMNS]


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def load_assessment_file(path, school_year, period, source="gcs"):
    """
    Load a single CRLA assessment CSV, harmonize its schema, and tag it
    with school-year and period metadata.

    Parameters
    ----------
    path : str
        File path — GCS bucket path when ``source='gcs'``,
        local filesystem path when ``source='local'``.
    school_year : str
        e.g. ``'2024-25'``.
    period : str
        ``'BoSY'`` or ``'EoSY'``.
    source : str
        ``'gcs'`` (default) or ``'local'``.

    Returns
    -------
    pandas.DataFrame
        Harmonized DataFrame with ``school_year`` and ``period`` columns.
    """
    if source == "gcs":
        fs = get_fs()
        with fs.open(str(path)) as f:
            df = pd.read_csv(f, low_memory=False)
    else:
        df = pd.read_csv(path, low_memory=False)

    df = harmonize_columns(df)
    df["school_year"] = school_year
    df["period"] = period
    return df


def load_all_assessments(file_map=None, source="gcs"):
    """
    Load every assessment file in *file_map*, harmonize, and return as a dict.

    Parameters
    ----------
    file_map : dict, optional
        ``{(school_year, period): path}``.  Defaults to ``CRLA_RAW_FILES``.
    source : str
        ``'gcs'`` or ``'local'``.

    Returns
    -------
    dict
        ``{(school_year, period): DataFrame}``
    """
    if file_map is None:
        file_map = CRLA_RAW_FILES

    results = {}
    for (sy, period), path in file_map.items():
        print(f"Loading {sy} {period} from {path} ...")
        results[(sy, period)] = load_assessment_file(
            path, sy, period, source=source
        )
        print(f"  → {len(results[(sy, period)])} schools loaded.")

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

METADATA_COLUMNS = ["School Name", "Region", "Division", "District"]

_total_assessed_cache = {}


def _get_group_columns(grade, lang):
    """Return the 5 canonical column names for a grade-language group."""
    if lang:
        return [f"{grade} {lang} {profile}" for profile in READING_PROFILES]
    return [f"{grade} {profile}" for profile in READING_PROFILES]


def _clean_raw_to_numeric(df):
    """Clean grade columns to numeric and index by School ID.

    Returns a copy with the 30 canonical grade columns cleaned
    (comma removal, ``pd.to_numeric`` coercion) and indexed by
    School ID.  All other columns are preserved.
    """
    df = df.copy()
    for col in CANONICAL_GRADE_COLUMNS:
        s = df[col].astype(str).str.replace(",", "", regex=False)
        df[col] = pd.to_numeric(s, errors="coerce")
    if "School ID" in df.columns:
        df = df.set_index("School ID")
    return df


# ---------------------------------------------------------------------------
# Percentage conversion
# ---------------------------------------------------------------------------

def compute_percentages(df):
    """
    Convert raw student counts to percentages per grade-language group.

    Takes a harmonized DataFrame (from ``load_assessment_file`` or
    ``harmonize_columns``) and returns a percentage DataFrame indexed
    by School ID.

    Numeric cleaning is applied first: commas are removed and values
    are coerced to numeric (non-parseable values become NaN).
    Within each of the 6 grade-language groups the 5 reading-profile
    counts are divided by their row-wise sum to produce percentages
    (0–100).  Groups with zero or all-NaN counts yield NaN.

    Parameters
    ----------
    df : pandas.DataFrame
        Harmonized DataFrame with raw counts in the 30 canonical
        grade columns.

    Returns
    -------
    pandas.DataFrame
        Indexed by ``School ID``.  Contains ``METADATA_COLUMNS``,
        ``school_year``, ``period``, and the 30 canonical columns
        now expressed as percentages.
    """
    df = _clean_raw_to_numeric(df)

    # Cache total assessed per school (sum of raw counts before percentage conversion)
    sy = df["school_year"].iloc[0]
    period = df["period"].iloc[0]
    _total_assessed_cache[(sy, period)] = df[CANONICAL_GRADE_COLUMNS].sum(axis=1)

    # Compute percentages per grade-language group
    for grade, lang in GRADE_LANGUAGE_GROUPS:
        group_cols = _get_group_columns(grade, lang)
        group_sum = df[group_cols].sum(axis=1)
        for col in group_cols:
            df[col] = (df[col] / group_sum * 100).where(group_sum > 0)

    # Keep useful columns
    tag_cols = ["school_year", "period"]
    keep = [
        c
        for c in METADATA_COLUMNS + CANONICAL_GRADE_COLUMNS + tag_cols
        if c in df.columns
    ]
    return df[keep]


# ---------------------------------------------------------------------------
# Per-time-point validation
# ---------------------------------------------------------------------------

def validate_timepoint(pct_df, raw_counts_df=None):
    """
    Validate per-school data completeness at a single time point.

    Parameters
    ----------
    pct_df : pandas.DataFrame
        Output of ``compute_percentages`` (indexed by School ID).
    raw_counts_df : pandas.DataFrame, optional
        Cleaned raw counts indexed by School ID (from
        ``_clean_raw_to_numeric``).  When provided, enables
        ``min_group_assessed`` and the sample-size component of
        ``valid_strict``.

    Returns
    -------
    pandas.DataFrame
        Indexed by School ID with columns:

        - ``has_{group}`` : bool for each of the 6 grade-language groups
        - ``groups_available`` : int (0–6)
        - ``valid`` : bool (True if at least one group has data)
        - ``has_all_grades`` : bool (at least one group per grade level)
        - ``min_group_assessed`` : int (minimum students across reporting groups)
        - ``valid_strict`` : bool (all grades covered, ≥4 groups, ≥20 per group)
    """
    validation = pd.DataFrame(index=pct_df.index)

    for grade, lang in GRADE_LANGUAGE_GROUPS:
        group_cols = _get_group_columns(grade, lang)
        label = f"{grade}_{lang}" if lang else grade
        validation[f"has_{label}"] = pct_df[group_cols].notna().any(axis=1)

    has_cols = [c for c in validation.columns if c.startswith("has_")]
    validation["groups_available"] = validation[has_cols].sum(axis=1)
    validation["valid"] = validation["groups_available"] > 0

    # ---- Strict validation tier ----

    # has_all_grades: at least one group per grade level
    has_g1 = validation["has_G1"]
    has_g2 = validation["has_G2_MT"] | validation["has_G2_Fil"]
    has_g3 = validation["has_G3_MT"] | validation["has_G3_Fil"] | validation["has_G3_Eng"]
    validation["has_all_grades"] = has_g1 & has_g2 & has_g3

    # min_group_assessed: minimum total assessed across reporting groups
    if raw_counts_df is not None:
        group_totals = []
        for grade, lang in GRADE_LANGUAGE_GROUPS:
            group_cols = _get_group_columns(grade, lang)
            label = f"{grade}_{lang}" if lang else grade
            group_sum = raw_counts_df.reindex(pct_df.index)[group_cols].sum(axis=1)
            group_sum[~validation[f"has_{label}"]] = np.nan
            group_totals.append(group_sum)
        validation["min_group_assessed"] = (
            pd.concat(group_totals, axis=1).min(axis=1).astype("Int64")
        )
    else:
        validation["min_group_assessed"] = np.nan

    # valid_strict: all grades + ≥4 groups + ≥15 per group
    strict = (
        validation["valid"]
        & validation["has_all_grades"]
        & (validation["groups_available"] >= 4)
    )
    if raw_counts_df is not None:
        strict = strict & (validation["min_group_assessed"] >= 15)
    validation["valid_strict"] = strict

    return validation


# ---------------------------------------------------------------------------
# Cached total assessed
# ---------------------------------------------------------------------------

def get_total_assessed(school_year, period):
    """
    Return the cached total assessed count per school for a timepoint.

    The cache is populated by ``compute_percentages()`` — call that first.

    Parameters
    ----------
    school_year : str
    period : str

    Returns
    -------
    pandas.Series
        Total student count per school, indexed by School ID.
    """
    key = (school_year, period)
    if key not in _total_assessed_cache:
        raise KeyError(
            f"Total assessed for {key} not cached. "
            f"Call compute_percentages() for this timepoint first. "
            f"Available: {list(_total_assessed_cache.keys())}"
        )
    return _total_assessed_cache[key]
