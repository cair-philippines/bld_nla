"""
RMA preprocessing: file discovery, schema normalization, silver writing,
and analytical helpers (ordinal moments, EMD).

RMA (Rapid Mathematics Assessment) covers Grades 1–10 in three key stages:
  KS1 (G1–G3): EoSY 2024-25 + BoSY/EoSY 2025-26 (3 timepoints)
  KS2 (G4–G6): 2025-26 (National Dashboard) only
  KS3 (G7–G10): 2025-26 (National Dashboard) only

Two KS1 files are excluded:
- 2023-24: different 3-level school-total-only schema, no per-grade breakdown.
- 2024-25 BoSY: School ID column not populated in the archive export (all '-').
  The 2024-25 EoSY archive has valid School IDs and is included.

Five proficiency levels, no language split:
  1  Emerging Not Proficient
  2  Emerging - Low Proficient
  3  Developing - Nearly Proficient
  4  Transitioning - Proficient
  5  At Grade Level - Highly Proficient
"""

import fnmatch
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BRONZE_RMA_DIR = PROJECT_ROOT / "data" / "bronze" / "rma"
SILVER_RMA_DIR = PROJECT_ROOT / "data" / "silver" / "rma"

RMA_METADATA_COLUMNS = ["School Name", "Region", "Division", "District"]

RMA_LEVELS = [
    "Emerging Not Proficient",
    "Emerging - Low Proficient",
    "Developing - Nearly Proficient",
    "Transitioning - Proficient",
    "At Grade Level - Highly Proficient",
]

RMA_ORDINAL_WEIGHTS = {level: i + 1 for i, level in enumerate(RMA_LEVELS)}

RMA_GRADES_BY_KS = {
    "ks1": ["G1", "G2", "G3"],
    "ks2": ["G4", "G5", "G6"],
    "ks3": ["G7", "G8", "G9", "G10"],
}

# Timepoints available per KS.
# KS1 2024-25 BoSY excluded: School ID column not populated in the archive export.
RMA_TIMEPOINTS_BY_KS = {
    "ks1": [("2024-25", "EoSY"), ("2025-26", "BoSY"), ("2025-26", "EoSY")],
    "ks2": [("2025-26", "BoSY"), ("2025-26", "EoSY")],
    "ks3": [("2025-26", "BoSY"), ("2025-26", "EoSY")],
}

# Glob hints keyed by (ks, school_year, period).
# Archive files follow "RMA KS1 Results Archive_SY {year} ..." (KS before Archive).
# Year is included in archive hints to distinguish 2024-25 from 2023-24 files.
# National dashboard files use "(KS1)" notation with parentheses.
_BRONZE_FILE_HINTS = {
    ("ks1", "2024-25", "EoSY"): "*KS1*Archive*2024-25*EoSY*",
    ("ks1", "2025-26", "BoSY"): "*(KS1)*BoSY*",
    ("ks1", "2025-26", "EoSY"): "*(KS1)*EoSY*",
    ("ks2", "2025-26", "BoSY"): "*(KS2)*BoSY*",
    ("ks2", "2025-26", "EoSY"): "*(KS2)*EoSY*",
    ("ks3", "2025-26", "BoSY"): "*(KS3)*BoSY*",
    ("ks3", "2025-26", "EoSY"): "*(KS3)*EoSY*",
}


def get_rma_group_columns(grade):
    """Return the 5 level column names for a grade."""
    return [f"{grade} {level}" for level in RMA_LEVELS]


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def resolve_rma_files(bronze_dir=None):
    """
    Scan the RMA bronze directory and return a file map.

    Returns
    -------
    dict
        {(ks, school_year, period): Path}
    """
    if bronze_dir is None:
        bronze_dir = BRONZE_RMA_DIR
    bronze_dir = Path(bronze_dir)

    result = {}
    for key, hint in _BRONZE_FILE_HINTS.items():
        matches = [f for f in bronze_dir.iterdir() if fnmatch.fnmatch(f.name, hint)]
        if not matches:
            print(f"  ⚠ No file found for {key} (hint: {hint})")
        elif len(matches) > 1:
            chosen = sorted(matches)[-1]
            print(f"  ⚠ Multiple matches for {key}: {[m.name for m in matches]}"
                  f" → using {chosen.name}")
            result[key] = chosen
        else:
            result[key] = matches[0]
    return result


# ---------------------------------------------------------------------------
# Loading and cleaning
# ---------------------------------------------------------------------------

def load_rma_file(path, ks, school_year, period):
    """
    Load a single RMA bronze CSV, clean numerics, and index by School ID.

    Per-grade level columns and Assessed counts are cleaned to numeric.
    'Total Assessed' (school-level) is preserved as 'total_assessed'.
    KS3 'Municipality' is renamed to 'District' for schema consistency.
    """
    df = pd.read_csv(path, low_memory=False)

    # Strip whitespace from string columns
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].str.strip()

    # KS3 uses 'Municipality' instead of 'District'
    if "Municipality" in df.columns and "District" not in df.columns:
        df = df.rename(columns={"Municipality": "District"})

    grades = RMA_GRADES_BY_KS[ks]
    grade_cols = []
    for grade in grades:
        grade_cols.append(f"{grade} Assessed")
        grade_cols.extend(get_rma_group_columns(grade))

    for col in grade_cols:
        if col in df.columns:
            s = df[col].astype(str).str.replace(",", "", regex=False).str.strip()
            df[col] = pd.to_numeric(s, errors="coerce")
        else:
            df[col] = np.nan

    if "Total Assessed" in df.columns:
        s = df["Total Assessed"].astype(str).str.replace(",", "", regex=False).str.strip()
        df["total_assessed"] = pd.to_numeric(s, errors="coerce")
    else:
        df["total_assessed"] = np.nan

    df["school_year"] = school_year
    df["period"] = period
    df["ks"] = ks

    keep_candidates = (
        ["School ID"] + RMA_METADATA_COLUMNS
        + ["total_assessed", "school_year", "period", "ks"]
        + grade_cols
    )
    keep = [c for c in keep_candidates if c in df.columns]
    df = df[keep].copy()

    if "School ID" in df.columns:
        df = df.set_index("School ID")

    return df


# ---------------------------------------------------------------------------
# Percentage conversion
# ---------------------------------------------------------------------------

def compute_rma_percentages(df, ks):
    """
    Convert per-grade raw counts to percentages (0–100).

    Denominator is the sum of the 5 level columns per grade (not {G} Assessed),
    consistent with the CRLA and PhilIRI approach. Groups with zero or
    all-NaN counts yield NaN for all levels in that group.

    Returns a copy with level columns replaced by percentages.
    """
    df = df.copy()
    for grade in RMA_GRADES_BY_KS[ks]:
        cols = get_rma_group_columns(grade)
        group_sum = df[cols].sum(axis=1)
        for col in cols:
            df[col] = (df[col] / group_sum * 100).where(group_sum > 0)
    return df


# ---------------------------------------------------------------------------
# Ordinal moments
# ---------------------------------------------------------------------------

def compute_rma_ordinal_moments(pct_df, ks):
    """
    Compute ordinal proficiency moments per school, averaged across grades.

    For each grade group with complete data (all 5 level columns non-NaN,
    non-zero denominator), computes mean, SD, skewness, excess kurtosis,
    and bimodality coefficient from the percentage distribution against
    ordinal positions [1, 2, 3, 4, 5].

    Returns
    -------
    pandas.DataFrame
        Columns: ordinal_mean, ordinal_sd, ordinal_skew, ordinal_kurt,
        bimodality_coef.  School-level values are means across grades.
    """
    w = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    grades = RMA_GRADES_BY_KS[ks]

    group_means, group_sds, group_skews, group_kurts, group_bcs = [], [], [], [], []

    for grade in grades:
        cols = get_rma_group_columns(grade)
        group_data = pct_df[cols]
        has_data = group_data.notna().all(axis=1) & (group_data.sum(axis=1) > 0)

        pct = group_data.values.astype(float)

        mean = (pct * w).sum(axis=1) / 100
        dev = w - mean[:, np.newaxis]
        var = (pct * dev ** 2).sum(axis=1) / 100
        sd = np.sqrt(var)

        with np.errstate(divide="ignore", invalid="ignore"):
            skew = (pct * dev ** 3).sum(axis=1) / 100 / (sd ** 3)
            kurt_reg = (pct * dev ** 4).sum(axis=1) / 100 / (sd ** 4)
            bc = (skew ** 2 + 1) / kurt_reg

        skew[sd == 0] = np.nan
        kurt_reg[sd == 0] = np.nan
        bc[sd == 0] = np.nan

        mask = ~has_data.values
        mean_s = pd.Series(mean, index=pct_df.index)
        sd_s = pd.Series(sd, index=pct_df.index)
        skew_s = pd.Series(skew, index=pct_df.index)
        kurt_s = pd.Series(kurt_reg - 3.0, index=pct_df.index)
        bc_s = pd.Series(bc, index=pct_df.index)

        for s in (mean_s, sd_s, skew_s, kurt_s, bc_s):
            s.values[mask] = np.nan

        group_means.append(mean_s)
        group_sds.append(sd_s)
        group_skews.append(skew_s)
        group_kurts.append(kurt_s)
        group_bcs.append(bc_s)

    return pd.DataFrame({
        "ordinal_mean": pd.concat(group_means, axis=1).mean(axis=1),
        "ordinal_sd": pd.concat(group_sds, axis=1).mean(axis=1),
        "ordinal_skew": pd.concat(group_skews, axis=1).mean(axis=1),
        "ordinal_kurt": pd.concat(group_kurts, axis=1).mean(axis=1),
        "bimodality_coef": pd.concat(group_bcs, axis=1).mean(axis=1),
    })


# ---------------------------------------------------------------------------
# Earth Mover's Distance
# ---------------------------------------------------------------------------

def compute_rma_emd(pct0, pct1, ks):
    """
    Mean Earth Mover's Distance (Wasserstein-1) per school between two timepoints.

    Computed per grade using ordinal positions [1, 2, 3, 4, 5] as the value
    axis and percentage vectors as weights.  School-level value is the mean
    across grades with complete data at both endpoints.

    Returns
    -------
    pandas.Series
        Indexed by the union of both School ID sets.
        NaN for schools missing from either timepoint or with no complete
        grade pairs at both endpoints.
    """
    w = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    grades = RMA_GRADES_BY_KS[ks]
    common = pct0.index.intersection(pct1.index)

    group_emds = []
    for grade in grades:
        cols = get_rma_group_columns(grade)
        g0 = pct0.reindex(common)[cols]
        g1 = pct1.reindex(common)[cols]

        has_data = (
            g0.notna().all(axis=1) & (g0.sum(axis=1) > 0) &
            g1.notna().all(axis=1) & (g1.sum(axis=1) > 0)
        )
        valid_idx = has_data[has_data].index

        emds = pd.Series(np.nan, index=common)
        if len(valid_idx) > 0:
            p0 = g0.loc[valid_idx].values / 100.0
            p1 = g1.loc[valid_idx].values / 100.0
            emd_vals = np.array([
                wasserstein_distance(w, w, p0[i], p1[i])
                for i in range(len(valid_idx))
            ])
            emds.loc[valid_idx] = emd_vals

        group_emds.append(emds)

    all_idx = pct0.index.union(pct1.index)
    return pd.concat(group_emds, axis=1).mean(axis=1).reindex(all_idx)


# ---------------------------------------------------------------------------
# Silver writer
# ---------------------------------------------------------------------------

def write_silver_rma(file_map=None, output_dir=None):
    """
    Load all RMA bronze files, clean, and write silver parquets.
    Output: one parquet per (ks, school_year, period) — {ks}_{sy}_{period}.parquet
    """
    if file_map is None:
        file_map = resolve_rma_files()
    if output_dir is None:
        output_dir = SILVER_RMA_DIR

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for (ks, sy, period), path in sorted(file_map.items()):
        print(f"  Loading {ks} {sy} {period} from {path.name} ...")
        df = load_rma_file(path, ks, sy, period)
        fname = f"{ks}_{sy}_{period}.parquet"
        out_path = out / fname
        df.to_parquet(out_path)
        print(f"    → {out_path} ({len(df)} schools)")
