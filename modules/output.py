"""
CRLA output: export pairwise progress CSVs matching the crla_v2.py format.

Each consecutive pair in the time chain produces one CSV with:
- Metadata (School Name, Region, Division, District)
- Validation flags (Has {period} Data, Student Count Mismatch, Valid for Progress Analysis)
- Performance scores at both endpoints + Progress Score (delta)
- Per-period breakdown: category averages, individual percentage columns, weighted columns
"""

import numpy as np
import pandas as pd
from pathlib import Path

from preprocessing import (
    READING_PROFILES,
    CANONICAL_GRADE_COLUMNS,
    METADATA_COLUMNS,
)
from analysis import _total_assessed, _segment_label, TIME_CHAIN


# Category order matching crla_v2.py output
_OUTPUT_CATEGORY_ORDER = [
    "Developing",
    "Transitioning",
    "Higher Emergent",
    "Lower Emergent",
    "Grade Level",
]


def _build_pair_dataframe(
    t0, t1, percentages, performance, validation, raw_data,
    weights, count_threshold,
):
    """
    Build a single results DataFrame for one consecutive pair,
    matching the crla_v2.py column layout.
    """
    sy0, period0 = t0
    sy1, period1 = t1
    label0 = f"{period0} {sy0}"
    label1 = f"{period1} {sy1}"

    # Collect all schools present in either endpoint
    schools0 = set(performance[t0].index) if t0 in performance else set()
    schools1 = set(performance[t1].index) if t1 in performance else set()
    idx = pd.Index(sorted(schools0 | schools1), name="School ID")

    result = pd.DataFrame(index=idx)

    # ---- Metadata (prefer t0, fill from t1) ----
    meta = pd.DataFrame(index=idx, columns=METADATA_COLUMNS)
    for key in [t0, t1]:
        if key not in raw_data:
            continue
        src = raw_data[key].copy()
        if "School ID" in src.columns:
            src = src.set_index("School ID")
        for col in METADATA_COLUMNS:
            if col not in src.columns:
                continue
            missing = meta[col].isna()
            fill = src[col].reindex(idx)
            meta.loc[missing, col] = fill[missing]
    for col in METADATA_COLUMNS:
        result[col] = meta[col]

    # ---- Validation flags ----
    val0 = (
        validation[t0]["valid"].reindex(idx, fill_value=False)
        if t0 in validation
        else pd.Series(False, index=idx)
    )
    val1 = (
        validation[t1]["valid"].reindex(idx, fill_value=False)
        if t1 in validation
        else pd.Series(False, index=idx)
    )

    # Count stability
    cnt0 = (
        _total_assessed(raw_data[t0]).reindex(idx)
        if t0 in raw_data
        else pd.Series(np.nan, index=idx)
    )
    cnt1 = (
        _total_assessed(raw_data[t1]).reindex(idx)
        if t1 in raw_data
        else pd.Series(np.nan, index=idx)
    )
    pct_change = (cnt1 - cnt0).abs() / cnt0
    count_mismatch = (pct_change > count_threshold).fillna(True)
    valid_for_progress = val0 & val1 & ~count_mismatch

    result[f"Has {label0} Data"] = val0
    result[f"Has {label1} Data"] = val1
    result["Student Count Mismatch"] = count_mismatch
    result["Valid for Progress Analysis"] = valid_for_progress

    # ---- Performance scores ----
    perf0 = (
        performance[t0].reindex(idx)
        if t0 in performance
        else pd.Series(np.nan, index=idx)
    )
    perf1 = (
        performance[t1].reindex(idx)
        if t1 in performance
        else pd.Series(np.nan, index=idx)
    )
    result[f"{label0} Performance"] = perf0
    result[f"{label1} Performance"] = perf1

    progress = perf1 - perf0
    progress[~valid_for_progress] = np.nan
    result["Progress Score"] = progress

    # ---- Per-period breakdown ----
    for key, label in [(t0, label0), (t1, label1)]:
        pct = (
            percentages[key].reindex(idx)
            if key in percentages
            else pd.DataFrame(index=idx, columns=CANONICAL_GRADE_COLUMNS)
        )

        # Category averages + individual columns
        for category in _OUTPUT_CATEGORY_ORDER:
            cat_cols = [c for c in CANONICAL_GRADE_COLUMNS if category in c]
            if cat_cols:
                result[f"{label} {category} %"] = pct[cat_cols].mean(axis=1)
                for col in cat_cols:
                    result[f"{label} {col}"] = pct[col]

        # Weighted columns (after all category breakdowns, matching crla_v2.py)
        if weights:
            for category in _OUTPUT_CATEGORY_ORDER:
                cat_cols = [c for c in CANONICAL_GRADE_COLUMNS if category in c]
                if cat_cols and category in weights:
                    cat_avg = pct[cat_cols].mean(axis=1)
                    result[f"{label} {category} Weighted"] = (
                        cat_avg * weights[category] / 100
                    )

    return result


def export_pairwise_csvs(
    percentages,
    performance,
    validation,
    raw_data,
    weights,
    time_chain=None,
    count_threshold=0.25,
    output_dir="output",
    filename_prefix="crla_progress_score.pca_derived",
):
    """
    Export one CSV per consecutive pair in the time chain.

    Each CSV matches the crla_v2.py output format: metadata, validation,
    performance scores, progress score, and per-period category breakdowns.

    Parameters
    ----------
    percentages : dict
        ``{(sy, period): DataFrame}`` from Step 2a.
    performance : dict
        ``{(sy, period): Series}`` from Step 2d.
    validation : dict
        ``{(sy, period): DataFrame}`` from Step 2b.
    raw_data : dict
        ``{(sy, period): DataFrame}`` from Step 1.
    weights : dict
        ``{reading_profile: weight}`` from Step 2c.
    time_chain : list of tuples, optional
        Ordered ``[(sy, period), ...]``.  Defaults to ``TIME_CHAIN``.
    count_threshold : float, optional
        Maximum acceptable proportional change in student count.
        Default 0.25 (25%).
    output_dir : str or Path, optional
        Directory for output CSVs. Created if it doesn't exist.

    Returns
    -------
    list of Path
        Paths to the exported CSV files.
    """
    if time_chain is None:
        time_chain = TIME_CHAIN

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exported = []

    for i in range(len(time_chain) - 1):
        t0 = time_chain[i]
        t1 = time_chain[i + 1]
        sy0, period0 = t0
        sy1, period1 = t1

        df = _build_pair_dataframe(
            t0, t1, percentages, performance, validation,
            raw_data, weights, count_threshold,
        )

        label = _segment_label(t0, t1)
        fname = f"{filename_prefix}.{label}.csv"
        fpath = output_dir / fname
        df.to_csv(fpath)
        exported.append(fpath)

        valid_n = df["Valid for Progress Analysis"].sum()
        print(
            f"Exported: {fname} "
            f"({len(df)} schools, {len(df.columns)} columns, "
            f"{valid_n} valid)"
        )

    return exported
