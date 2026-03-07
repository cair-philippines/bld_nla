"""
CRLA analysis: PCA weight derivation, performance scoring,
multi-timepoint processing, and chain-based progress scoring.
"""

import numpy as np
import pandas as pd

from preprocessing import (
    READING_PROFILES,
    CANONICAL_GRADE_COLUMNS,
    GRADE_LANGUAGE_GROUPS,
    METADATA_COLUMNS,
    _get_group_columns,
    compute_percentages,
    validate_timepoint,
)


# ---------------------------------------------------------------------------
# Default time chain
# ---------------------------------------------------------------------------

TIME_CHAIN = [
    ("2024-25", "BoSY"),
    ("2024-25", "EoSY"),
    ("2025-26", "BoSY"),
]


# ---------------------------------------------------------------------------
# PCA weight derivation
# ---------------------------------------------------------------------------

def derive_pca_weights(pct_df, validation, invert=False):
    """
    Derive reading-profile weights from PCA on a single reference
    time point.

    Fits PCA (1 component) on the 30 standardized percentage columns
    of valid schools, then maps PC1 loadings to category-level weights
    scaled 0–100.

    Parameters
    ----------
    pct_df : pandas.DataFrame
        Percentage DataFrame for the reference time point (from
        ``compute_percentages``), indexed by School ID.
    validation : pandas.DataFrame
        Per-timepoint validation for the same time point (from
        ``validate_timepoint``).
    invert : bool, optional
        If True, invert weight direction for all categories except
        Grade Level when Developing has a lower loading than Lower
        Emergent.

    Returns
    -------
    dict
        ``{reading_profile: weight}`` with values in 0–100.
    pca : sklearn.decomposition.PCA
        Fitted PCA model (for inspection / explained variance).
    """
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    # Filter to valid schools
    valid_idx = validation[validation["valid"]].index
    data = pct_df.loc[pct_df.index.isin(valid_idx), CANONICAL_GRADE_COLUMNS]

    if len(valid_idx) < 10:
        print(
            f"Warning: Only {len(valid_idx)} valid schools. "
            "PCA results may not be reliable."
        )

    # Drop rows with any NaN (PCA requires complete cases)
    X = data.dropna()
    if X.shape[0] < 5:
        raise ValueError(
            f"Only {X.shape[0]} complete rows available for PCA. "
            "Cannot derive meaningful weights."
        )

    # Standardize and fit PCA
    X_scaled = StandardScaler().fit_transform(X)
    pca = PCA(n_components=1)
    pca.fit(X_scaled)

    loadings = pca.components_[0]

    # Map loadings to categories (average across columns per category)
    category_loadings = {}
    col_idx = 0
    for profile in READING_PROFILES:
        profile_cols = [c for c in CANONICAL_GRADE_COLUMNS if profile in c]
        n = len(profile_cols)
        category_loadings[profile] = np.mean(loadings[col_idx : col_idx + n])
        col_idx += n

    # Optional inversion
    if invert:
        if (
            "Developing" in category_loadings
            and "Lower Emergent" in category_loadings
            and category_loadings["Developing"]
            < category_loadings["Lower Emergent"]
        ):
            for cat in category_loadings:
                if cat != "Grade Level":
                    category_loadings[cat] = -category_loadings[cat]

    # Scale to 0–100
    min_l = min(category_loadings.values())
    max_l = max(category_loadings.values())
    weights = {
        cat: round(100 * (val - min_l) / (max_l - min_l))
        for cat, val in category_loadings.items()
    }

    print("PCA-derived weights:")
    for cat in READING_PROFILES:
        print(f"  {cat}: {weights[cat]}")
    print(
        f"  Explained variance: {pca.explained_variance_ratio_[0]:.4f}"
    )
    print(f"  Fitted on {X.shape[0]} complete schools")

    return weights, pca


# ---------------------------------------------------------------------------
# Performance scoring
# ---------------------------------------------------------------------------

def compute_performance_score(pct_df, weights):
    """
    Compute a weighted performance score per school.

    For each reading-profile category the weight is applied equally to
    every column belonging to that category.  Schools with partial data
    are scored only on columns that are present; the divisor adjusts so
    scores remain comparable.

    Parameters
    ----------
    pct_df : pandas.DataFrame
        Percentage DataFrame indexed by School ID.
    weights : dict
        ``{reading_profile: weight}``.  **Required** — equal weights
        produce degenerate scores.

    Returns
    -------
    pandas.Series
        Performance score per school, indexed by School ID.
        NaN for schools with no usable data.
    """
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

def process_all_timepoints(df_all, weights=None, pca_reference=None,
                           pca_invert=False):
    """
    Run the full Step 2 pipeline (2a → 2b → 2c → 2d).

    1. ``compute_percentages`` for every time point.
    2. ``validate_timepoint`` for every time point.
    3. Derive PCA weights from *pca_reference* (or use provided *weights*).
    4. ``compute_performance_score`` for every time point.

    Exactly one of *weights* or *pca_reference* must be provided.
    Equal weights are not supported (they produce degenerate scores).

    Parameters
    ----------
    df_all : dict
        ``{(school_year, period): DataFrame}`` from
        ``load_all_assessments``.
    weights : dict, optional
        Pre-computed reading-profile weights.  If provided,
        *pca_reference* is ignored.
    pca_reference : tuple, optional
        ``(school_year, period)`` key indicating which time point to
        use for PCA weight derivation.  Must be a key in *df_all*.
    pca_invert : bool, optional
        Passed to ``derive_pca_weights``.

    Returns
    -------
    dict with keys:
        ``percentages``  : ``{(sy, period): DataFrame}``
        ``validation``   : ``{(sy, period): DataFrame}``
        ``weights``      : ``dict`` of PCA or provided weights
        ``pca_model``    : PCA model (or None if weights provided)
        ``performance``  : ``{(sy, period): Series}``
    """
    if weights is None and pca_reference is None:
        raise ValueError(
            "Either 'weights' or 'pca_reference' must be provided. "
            "Equal weights produce degenerate scores (always 20.00)."
        )

    if pca_reference is not None and pca_reference not in df_all:
        raise KeyError(
            f"pca_reference {pca_reference} not found in df_all. "
            f"Available keys: {list(df_all.keys())}"
        )

    # 2a + 2b: percentages and validation for all time points
    percentages = {}
    validation = {}
    for key, df in df_all.items():
        percentages[key] = compute_percentages(df)
        validation[key] = validate_timepoint(percentages[key])
        sy, period = key
        valid_n = validation[key]["valid"].sum()
        print(f"{sy} {period}: {valid_n}/{len(validation[key])} schools valid")

    # 2c: weights
    pca_model = None
    if weights is None:
        print(f"\nDeriving PCA weights from {pca_reference} ...")
        weights, pca_model = derive_pca_weights(
            percentages[pca_reference],
            validation[pca_reference],
            invert=pca_invert,
        )

    # 2d: performance scoring
    performance = {}
    print()
    for key, pct in percentages.items():
        perf = compute_performance_score(pct, weights)
        # Mask invalid schools
        perf[~validation[key]["valid"]] = np.nan
        performance[key] = perf

        sy, period = key
        print(f"{sy} {period}: mean perf = {perf.mean():.2f}")

    return {
        "percentages": percentages,
        "validation": validation,
        "weights": weights,
        "pca_model": pca_model,
        "performance": performance,
    }


# ---------------------------------------------------------------------------
# Step 3 — Chain-based progress scoring
# ---------------------------------------------------------------------------

def _total_assessed(df):
    """
    Sum of all 30 grade-level columns per school, cleaned to numeric.

    Parameters
    ----------
    df : pandas.DataFrame
        Harmonized raw DataFrame (from ``load_assessment_file``).

    Returns
    -------
    pandas.Series
        Total student count per school, indexed by School ID.
    """
    tmp = df.copy()
    for col in CANONICAL_GRADE_COLUMNS:
        s = tmp[col].astype(str).str.replace(",", "", regex=False)
        tmp[col] = pd.to_numeric(s, errors="coerce")

    if "School ID" in tmp.columns:
        tmp = tmp.set_index("School ID")

    return tmp[CANONICAL_GRADE_COLUMNS].sum(axis=1)


def _segment_label(t0, t1):
    """
    Generate a human-readable label for a consecutive pair.

    BoSY → EoSY (same year)  → ``Learning_2024-25``
    EoSY → BoSY (next year)  → ``Retention_2024-25_to_2025-26``
    """
    sy0, period0 = t0
    sy1, period1 = t1
    if period0 == "BoSY" and period1 == "EoSY" and sy0 == sy1:
        return f"Learning_{sy0}"
    if period0 == "EoSY" and period1 == "BoSY":
        return f"Retention_{sy0}_to_{sy1}"
    return f"{period0}_{sy0}_to_{period1}_{sy1}"


def compute_chain_progress(
    performance,
    raw_data,
    validation,
    time_chain=None,
    count_threshold=0.25,
):
    """
    Compute pairwise segment deltas and composite progress across an
    ordered time chain, with cross-timepoint validation built in.

    For each consecutive pair ``(t_i, t_{i+1})`` in *time_chain*:

    1. Check both endpoints have valid per-timepoint data.
    2. Check raw student count stability (``count_threshold``).
    3. If valid, segment delta = ``perf(t_{i+1}) - perf(t_i)``.

    Parameters
    ----------
    performance : dict
        ``{(sy, period): Series}`` — performance scores from Step 2d.
    raw_data : dict
        ``{(sy, period): DataFrame}`` — harmonized DataFrames from
        Step 1 (used for student count stability checks).
    validation : dict
        ``{(sy, period): DataFrame}`` — per-timepoint validation from
        Step 2b.
    time_chain : list of tuples, optional
        Ordered ``[(sy, period), ...]``.  Defaults to ``TIME_CHAIN``.
    count_threshold : float, optional
        Maximum acceptable proportional change in total student count
        between adjacent time points.  Default 0.25 (25%).

    Returns
    -------
    pandas.DataFrame
        One row per school (union of all schools across all time
        points).  Columns include metadata, performance at each time
        point, segment deltas, segment validity flags,
        ``segments_available``, and ``composite_score``.
    """
    if time_chain is None:
        time_chain = TIME_CHAIN

    # ---- Collect all school IDs across the chain ----
    all_schools = set()
    for key in time_chain:
        if key in performance:
            all_schools |= set(performance[key].index)

    idx = pd.Index(sorted(all_schools), name="School ID")
    result = pd.DataFrame(index=idx)

    # ---- Metadata (from first available time point per school) ----
    meta = pd.DataFrame(index=idx, columns=METADATA_COLUMNS)
    for key in time_chain:
        if key not in raw_data:
            continue
        src = raw_data[key].copy()
        if "School ID" in src.columns:
            src = src.set_index("School ID")
        avail = [c for c in METADATA_COLUMNS if c in src.columns]
        for col in avail:
            missing = meta[col].isna()
            fill = src[col].reindex(meta.index)
            meta.loc[missing, col] = fill[missing]
    for col in METADATA_COLUMNS:
        result[col] = meta[col]

    # ---- Performance at each time point ----
    perf_cols = []
    for key in time_chain:
        sy, period = key
        col = f"perf_{period}_{sy}"
        perf_cols.append(col)
        if key in performance:
            result[col] = performance[key].reindex(idx)
        else:
            result[col] = np.nan

    # ---- Segments ----
    seg_delta_cols = []
    seg_valid_cols = []

    for i in range(len(time_chain) - 1):
        t0 = time_chain[i]
        t1 = time_chain[i + 1]
        label = _segment_label(t0, t1)
        seg_n = i + 1

        delta_col = f"seg{seg_n}_{label}"
        valid_col = f"seg{seg_n}_valid"
        count_col = f"seg{seg_n}_count_stable"

        # Performance at both endpoints
        perf0 = performance[t0].reindex(idx) if t0 in performance else pd.Series(np.nan, index=idx)
        perf1 = performance[t1].reindex(idx) if t1 in performance else pd.Series(np.nan, index=idx)

        # Per-timepoint validity at both endpoints
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
        both_valid = val0 & val1

        # Count stability
        cnt0 = _total_assessed(raw_data[t0]).reindex(idx) if t0 in raw_data else pd.Series(np.nan, index=idx)
        cnt1 = _total_assessed(raw_data[t1]).reindex(idx) if t1 in raw_data else pd.Series(np.nan, index=idx)
        pct_change = (cnt1 - cnt0).abs() / cnt0
        count_stable = (pct_change <= count_threshold).fillna(False)

        # Segment validity = both endpoints valid AND count stable
        seg_valid = both_valid & count_stable

        # Delta
        delta = perf1 - perf0
        delta[~seg_valid] = np.nan

        result[delta_col] = delta
        result[valid_col] = seg_valid
        result[count_col] = count_stable

        seg_delta_cols.append(delta_col)
        seg_valid_cols.append(valid_col)

    # ---- Summary ----
    result["segments_available"] = result[seg_valid_cols].sum(axis=1)
    result["composite_score"] = result[seg_delta_cols].sum(
        axis=1, min_count=1
    )

    # ---- Print summary ----
    n_total = len(result)
    for i, col in enumerate(seg_delta_cols):
        n_valid = result[seg_valid_cols[i]].sum()
        mean_delta = result[col].mean()
        print(
            f"Segment {i+1} ({col}): "
            f"{n_valid}/{n_total} schools valid, "
            f"mean delta = {mean_delta:.4f}"
        )

    full_chain = result["segments_available"] == len(seg_valid_cols)
    print(
        f"\nFull chain ({len(seg_valid_cols)} segments): "
        f"{full_chain.sum()}/{n_total} schools"
    )
    composite_valid = result["composite_score"].notna()
    print(
        f"Composite score: {composite_valid.sum()} schools scored, "
        f"mean = {result['composite_score'].mean():.4f}"
    )

    return result
