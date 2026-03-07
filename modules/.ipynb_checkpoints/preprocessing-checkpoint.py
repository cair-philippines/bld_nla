"""
CRLA preprocessing: schema harmonization and file loading.

Normalizes raw CRLA CSVs from different school years into an identical
column schema so downstream analysis is year-agnostic.
"""

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
    2. Drop grade-level "Total" columns (e.g. ``G1 Total Assessed``,
       ``G2 Total MT Assessed``) that vary between years.
    3. Reorder grade-level columns to a canonical order so that
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

    # 2. Separate non-grade and grade columns
    grade_cols = [c for c in df.columns if c.startswith("G")]
    non_grade_cols = [c for c in df.columns if not c.startswith("G")]

    # 3. Drop grade-level Total columns
    grade_cols = [c for c in grade_cols if "total" not in c.lower()]

    # 4. Validate all canonical columns are present
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

    # 5. Reorder: non-grade columns first, then canonical grade order
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
