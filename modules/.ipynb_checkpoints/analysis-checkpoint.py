"""
CRLA analysis: performance scoring and multi-timepoint processing.
"""

import numpy as np
import pandas as pd

from preprocessing import (
    READING_PROFILES,
    CANONICAL_GRADE_COLUMNS,
    METADATA_COLUMNS,
    compute_percentages,
    validate_timepoint,
)


# ---------------------------------------------------------------------------
# Performance scoring
# ---------------------------------------------------------------------------

def compute_performance_score(pct_df, weights=None):
    """
    Compute a weighted performance score per school from percentage data.

    For each reading-profile category the weight is applied equally to
    every column that belongs to that category (across all grade-language
    groups).  Schools with partial data are scored only on the columns
    that are present; the divisor adjusts so scores remain comparable.

    With default equal weights the score equals the simple mean of all
    non-NaN percentage values.

    Parameters
    ----------
    pct_df : pandas.DataFrame
        Percentage DataFrame indexed by School ID (from
        ``compute_percentages``).
    weights : dict, optional
        ``{reading_profile: weight}``.  Defaults to 100 for every
        profile (equal weighting).

    Returns
    -------
    pandas.Series
        Performance score per school, indexed by School ID.
        NaN for schools with no usable data.
    """
    if weights is None:
        weights = {p: 100 for p in READING_PROFILES}

    scores = pd.Series(0.0, index=pct_df.index)
    divisor = pd.Series(0.0, index=pct_df.index)

    for profile, weight in weights.items():
        profile_cols = [c for c in CANONICAL_GRADE_COLUMNS if profile in c]
        for col in profile_cols:
            valid = pct_df[col].notna()
            scores[valid] += pct_df.loc[valid, col] * weight / 100
            divisor[valid] += weight

    result = scores / (divisor / 100)
    result[divisor == 0] = np.nan
    return result


# ---------------------------------------------------------------------------
# Full Step-2 pipeline
# ---------------------------------------------------------------------------

def process_all_timepoints(df_all, weights=None):
    """
    Run the full Step 2 pipeline on every loaded time point.

    For each ``(school_year, period)`` in *df_all*:

    1. Convert raw counts → percentages.
    2. Validate per-school data completeness.
    3. Compute weighted performance score.

    Parameters
    ----------
    df_all : dict
        ``{(school_year, period): DataFrame}`` from
        ``load_all_assessments``.
    weights : dict, optional
        Reading-profile weights passed to
        ``compute_performance_score``.

    Returns
    -------
    dict
        ``percentages``  : ``{(sy, period): DataFrame}``
        ``validation``   : ``{(sy, period): DataFrame}``
        ``performance``  : ``{(sy, period): Series}``
    """
    percentages = {}
    validation = {}
    performance = {}

    for key, df in df_all.items():
        pct = compute_percentages(df)
        val = validate_timepoint(pct)
        perf = compute_performance_score(pct, weights)

        # Mask performance for invalid schools
        perf[~val["valid"]] = np.nan

        percentages[key] = pct
        validation[key] = val
        performance[key] = perf

        sy, period = key
        valid_n = val["valid"].sum()
        total_n = len(val)
        print(
            f"{sy} {period}: {valid_n}/{total_n} schools valid, "
            f"mean perf = {perf.mean():.2f}"
        )

    return {
        "percentages": percentages,
        "validation": validation,
        "performance": performance,
    }
