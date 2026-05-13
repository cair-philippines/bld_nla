"""
CRLA analysis: PCA weight derivation, ordinal proficiency scoring,
performance scoring, multi-timepoint processing, and chain-based
progress scoring.
"""

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance

from preprocessing import (
    READING_PROFILES,
    CANONICAL_GRADE_COLUMNS,
    GRADE_LANGUAGE_GROUPS,
    METADATA_COLUMNS,
    _get_group_columns,
    _clean_raw_to_numeric,
    compute_percentages,
    validate_timepoint,
    get_total_assessed,
)


# ---------------------------------------------------------------------------
# Time chain configuration
# ---------------------------------------------------------------------------

# Per-school-year chains. Segments are generated within each school year only
# (no cross-year segments). MoSY is an optional mid-year checkpoint for
# intervention schools.
SCHOOL_YEAR_CHAINS = {
    "2024-25": [("2024-25", "BoSY"), ("2024-25", "EoSY")],
    "2025-26": [("2025-26", "BoSY"), ("2025-26", "MoSY"), ("2025-26", "EoSY")],
}

# Flat list of all timepoints (union), used for data loading and iteration.
ALL_TIMEPOINTS = [tp for chain in SCHOOL_YEAR_CHAINS.values() for tp in chain]

# Legacy alias — kept for backward compatibility with downstream code that
# imports TIME_CHAIN. Points to ALL_TIMEPOINTS.
TIME_CHAIN = ALL_TIMEPOINTS


# ---------------------------------------------------------------------------
# Ordinal proficiency scoring
# ---------------------------------------------------------------------------

ORDINAL_WEIGHTS = {
    "Lower Emergent": 1,
    "Higher Emergent": 2,
    "Developing": 3,
    "Transitioning": 4,
    "Grade Level": 5,
}


def compute_ordinal_score(pct_df):
    """
    Compute ordinal proficiency index per school.

    For each grade-language group, computes a weighted average proficiency
    level using fixed ordinal weights:

        score = (1 × %LE + 2 × %HE + 3 × %Dev + 4 × %Trans + 5 × %GL) / 100

    The school-level score is the mean across all available groups.

    Parameters
    ----------
    pct_df : pandas.DataFrame
        Percentage DataFrame indexed by School ID (from
        ``compute_percentages``).

    Returns
    -------
    pandas.Series
        Ordinal proficiency score per school, in [1, 5].
        1 = all students at Lower Emergent.
        5 = all students at Grade Level.
        NaN if no complete groups available.
    """
    ordinal_vals = list(ORDINAL_WEIGHTS.values())  # [1, 2, 3, 4, 5]

    group_scores = []
    for grade, lang in GRADE_LANGUAGE_GROUPS:
        cols = _get_group_columns(grade, lang)
        group_data = pct_df[cols]
        has_data = group_data.notna().all(axis=1)

        score = sum(
            group_data[col] * w for col, w in zip(cols, ordinal_vals)
        ) / 100
        score[~has_data] = np.nan
        group_scores.append(score)

    return pd.concat(group_scores, axis=1).mean(axis=1)


def compute_ordinal_moments(pct_df):
    """
    Compute ordinal proficiency moments (mean, SD, skewness, excess kurtosis,
    bimodality coefficient) per school.

    For each grade-language group with complete data (all 5 profiles
    non-NaN), computes five moments from the percentage distribution
    and ordinal weights [1, 2, 3, 4, 5]:

        mean      = Σ(pct_i × w_i) / 100
        var       = Σ(pct_i × (w_i − mean)²) / 100
        sd        = √var
        skew      = [Σ(pct_i × (w_i − mean)³) / 100] / sd³
        kurt_reg  = [Σ(pct_i × (w_i − mean)⁴) / 100] / sd⁴   (regular kurtosis)
        kurt      = kurt_reg − 3                                (excess kurtosis)
        BC        = (skew² + 1) / kurt_reg

    BC (Bimodality Coefficient) > 0.555 is the conventional flag for
    bimodal character. High BC + low absolute skewness indicates symmetric
    spread across extremes (bimodal); low BC + high absolute skewness
    indicates strong unimodal concentration.

    School-level values are the mean of each moment across available
    grade-language groups.

    Parameters
    ----------
    pct_df : pandas.DataFrame
        Percentage DataFrame indexed by School ID.

    Returns
    -------
    pandas.DataFrame
        Columns: ``ordinal_mean``, ``ordinal_sd``, ``ordinal_skew``,
        ``ordinal_kurt`` (excess kurtosis), ``bimodality_coef``.
        ``ordinal_mean`` is identical to ``compute_ordinal_score()`` output.
    """
    w = np.array(list(ORDINAL_WEIGHTS.values()), dtype=float)

    group_means = []
    group_sds = []
    group_skews = []
    group_kurts = []
    group_bcs = []

    for grade, lang in GRADE_LANGUAGE_GROUPS:
        cols = _get_group_columns(grade, lang)
        group_data = pct_df[cols]
        has_data = group_data.notna().all(axis=1)

        pct = group_data.values  # (n_schools, 5)

        mean = (pct * w).sum(axis=1) / 100
        dev = w - mean[:, np.newaxis]  # (n_schools, 5)
        var = (pct * dev ** 2).sum(axis=1) / 100
        sd = np.sqrt(var)

        with np.errstate(divide="ignore", invalid="ignore"):
            skew = (pct * dev ** 3).sum(axis=1) / 100 / (sd ** 3)
            kurt_reg = (pct * dev ** 4).sum(axis=1) / 100 / (sd ** 4)
            bc = (skew ** 2 + 1) / kurt_reg

        skew[sd == 0] = np.nan
        kurt_reg[sd == 0] = np.nan
        bc[sd == 0] = np.nan

        mask = ~has_data
        mean_s = pd.Series(mean, index=pct_df.index)
        sd_s = pd.Series(sd, index=pct_df.index)
        skew_s = pd.Series(skew, index=pct_df.index)
        kurt_s = pd.Series(kurt_reg - 3.0, index=pct_df.index)
        bc_s = pd.Series(bc, index=pct_df.index)

        for s in (mean_s, sd_s, skew_s, kurt_s, bc_s):
            s[mask] = np.nan

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

def compute_emd(pct_df_t0, pct_df_t1):
    """
    Compute mean Earth Mover's Distance (Wasserstein-1) per school between
    two timepoints.

    For each school present in both timepoints, and for each grade-language
    group with complete data at both endpoints, computes the Wasserstein
    distance between the two ordinal distributions using ordinal positions
    [1, 2, 3, 4, 5] as the value axis and percentage vectors as weights.

    EMD = 0 means the distribution is identical at both timepoints.
    EMD = 4 is the theoretical maximum (all mass moves from position 1 to 5
    or vice versa).

    Parameters
    ----------
    pct_df_t0 : pandas.DataFrame
        Percentage DataFrame (from ``compute_percentages``) for the
        earlier timepoint. Indexed by School ID.
    pct_df_t1 : pandas.DataFrame
        Percentage DataFrame for the later timepoint. Indexed by School ID.

    Returns
    -------
    pandas.Series
        Mean EMD across available grade-language groups per school,
        indexed by the union of both School ID sets.
        NaN for schools missing from either timepoint or with no complete
        group pairs.
    """
    w = np.array(list(ORDINAL_WEIGHTS.values()), dtype=float)  # [1,2,3,4,5]
    common = pct_df_t0.index.intersection(pct_df_t1.index)

    group_emds = []
    for grade, lang in GRADE_LANGUAGE_GROUPS:
        cols = _get_group_columns(grade, lang)

        g0 = pct_df_t0.reindex(common)[cols]
        g1 = pct_df_t1.reindex(common)[cols]

        has_data = g0.notna().all(axis=1) & g1.notna().all(axis=1)
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

    all_idx = pct_df_t0.index.union(pct_df_t1.index)
    return pd.concat(group_emds, axis=1).mean(axis=1).reindex(all_idx)


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
                           pca_invert=False, scoring="pca"):
    """
    Run the full Step 2 pipeline (2a → 2b → 2c → 2d).

    1. ``compute_percentages`` for every time point.
    2. ``validate_timepoint`` for every time point.
    3. Derive weights (PCA, provided, or ordinal).
    4. Compute performance score for every time point.

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
    scoring : str, optional
        ``'pca'`` (default) or ``'ordinal'``.
        - ``'pca'``: requires *weights* or *pca_reference*.
        - ``'ordinal'``: uses fixed ordinal proficiency index (1–5).
          No weights or pca_reference needed.

    Returns
    -------
    dict with keys:
        ``percentages``  : ``{(sy, period): DataFrame}``
        ``validation``   : ``{(sy, period): DataFrame}``
        ``weights``      : ``dict`` of weights used
        ``pca_model``    : PCA model (or None)
        ``performance``  : ``{(sy, period): Series}``
        ``scoring``      : ``str`` scoring method used
    """
    if scoring not in ("pca", "ordinal"):
        raise ValueError(f"scoring must be 'pca' or 'ordinal', got {scoring!r}")

    if scoring == "pca" and weights is None and pca_reference is None:
        raise ValueError(
            "Either 'weights' or 'pca_reference' must be provided "
            "when scoring='pca'. "
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
    raw_counts = {}
    for key, df in df_all.items():
        percentages[key] = compute_percentages(df)
        raw_counts[key] = _clean_raw_to_numeric(df)
        validation[key] = validate_timepoint(percentages[key], raw_counts_df=raw_counts[key])
        sy, period = key
        valid_n = validation[key]["valid"].sum()
        strict_n = validation[key]["valid_strict"].sum()
        total_n = len(validation[key])
        print(f"{sy} {period}: {valid_n}/{total_n} valid, {strict_n}/{total_n} valid_strict")

    # 2c + 2d: weights and performance scoring
    pca_model = None

    if scoring == "ordinal":
        weights = ORDINAL_WEIGHTS
        print("\nUsing ordinal proficiency scoring (1–5 scale)")

        performance = {}
        ordinal_sd = {}
        ordinal_skew = {}
        ordinal_kurt = {}
        ordinal_bc = {}
        for key, pct in percentages.items():
            moments = compute_ordinal_moments(pct)
            invalid = ~validation[key]["valid"]

            perf = moments["ordinal_mean"]
            sd = moments["ordinal_sd"]
            skew = moments["ordinal_skew"]
            kurt = moments["ordinal_kurt"]
            bc = moments["bimodality_coef"]
            for col in (perf, sd, skew, kurt, bc):
                col[invalid] = np.nan

            performance[key] = perf
            ordinal_sd[key] = sd
            ordinal_skew[key] = skew
            ordinal_kurt[key] = kurt
            ordinal_bc[key] = bc

            sy, period = key
            print(f"{sy} {period}: mean={perf.mean():.2f}, sd={sd.mean():.2f}, "
                  f"skew={skew.mean():.2f}, bc={bc.mean():.3f}")
    else:
        # PCA path
        if weights is None:
            print(f"\nDeriving PCA weights from {pca_reference} ...")
            weights, pca_model = derive_pca_weights(
                percentages[pca_reference],
                validation[pca_reference],
                invert=pca_invert,
            )

        performance = {}
        print()
        for key, pct in percentages.items():
            perf = compute_performance_score(pct, weights)
            perf[~validation[key]["valid"]] = np.nan
            performance[key] = perf

            sy, period = key
            print(f"{sy} {period}: mean perf = {perf.mean():.2f}")

    result = {
        "percentages": percentages,
        "validation": validation,
        "weights": weights,
        "pca_model": pca_model,
        "performance": performance,
        "scoring": scoring,
    }

    if scoring == "ordinal":
        result["ordinal_sd"] = ordinal_sd
        result["ordinal_skew"] = ordinal_skew
        result["ordinal_kurt"] = ordinal_kurt
        result["ordinal_bc"] = ordinal_bc

    return result


# ---------------------------------------------------------------------------
# Step 3 — Chain-based progress scoring
# ---------------------------------------------------------------------------

def _total_assessed(df):
    """
    Retrieve cached total assessed count per school.

    Delegates to ``preprocessing.get_total_assessed()`` using the
    school_year and period metadata from the DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        Harmonized raw DataFrame (from ``load_assessment_file``).

    Returns
    -------
    pandas.Series
        Total student count per school, indexed by School ID.
    """
    sy = df["school_year"].iloc[0]
    period = df["period"].iloc[0]
    return get_total_assessed(sy, period)


def _segment_label(t0, t1):
    """
    Generate a human-readable label for a segment pair.

    Within-year:
        BoSY → EoSY (same year)  → ``Learning_2024-25``
        BoSY → MoSY (same year)  → ``BoSYMoSY_2025-26``
        MoSY → EoSY (same year)  → ``MoSYEoSY_2025-26``
    Year-over-year (same period):
        BoSY → BoSY             → ``YoY_BoSY_2024-25_to_2025-26``
        EoSY → EoSY             → ``YoY_EoSY_2024-25_to_2025-26``
    End-to-end:
        BoSY → EoSY (diff year) → ``EndToEnd_2024-25_to_2025-26``
    """
    sy0, period0 = t0
    sy1, period1 = t1
    if sy0 == sy1:
        if period0 == "BoSY" and period1 == "EoSY":
            return f"Learning_{sy0}"
        if period0 == "BoSY" and period1 == "MoSY":
            return f"BoSYMoSY_{sy0}"
        if period0 == "MoSY" and period1 == "EoSY":
            return f"MoSYEoSY_{sy0}"
    else:
        if period0 == period1:
            return f"YoY_{period0}_{sy0}_to_{sy1}"
        if period0 == "BoSY" and period1 == "EoSY":
            return f"EndToEnd_{sy0}_to_{sy1}"
    return f"{period0}_{sy0}_to_{period1}_{sy1}"


def _build_segment_pairs(school_year_chains=None):
    """
    Build the list of all logical segment pairs.

    Generates:
    1. Within-year consecutive pairs (BoSY→MoSY, MoSY→EoSY)
    2. Within-year spanning pairs (BoSY→EoSY when MoSY exists)
    3. Year-over-year same-period pairs (BoSY→BoSY, EoSY→EoSY)
    4. End-to-end pair (first BoSY → last EoSY)

    Returns
    -------
    list of (t0, t1) tuples
        Each element is a pair of (school_year, period) tuples defining
        a segment.
    """
    if school_year_chains is None:
        school_year_chains = SCHOOL_YEAR_CHAINS

    pairs = []
    sorted_sys = sorted(school_year_chains.keys())

    # ── Within-year pairs ──
    for sy in sorted_sys:
        chain = school_year_chains[sy]
        available = [tp for tp in chain]
        if len(available) < 2:
            continue

        # Consecutive pairs
        for i in range(len(available) - 1):
            pairs.append((available[i], available[i + 1]))

        # Spanning pair: BoSY→EoSY if there's an intermediate (MoSY)
        if len(available) > 2:
            first, last = available[0], available[-1]
            if (first, last) not in pairs:
                pairs.append((first, last))

    # ── Cross-year pairs (only if multiple school years) ──
    if len(sorted_sys) >= 2:
        # Collect all timepoints by period across school years
        by_period = {}
        for sy in sorted_sys:
            for tp in school_year_chains[sy]:
                _, period = tp
                by_period.setdefault(period, []).append(tp)

        # Year-over-year same-period pairs (BoSY→BoSY, EoSY→EoSY)
        for period in ["BoSY", "EoSY"]:
            tps = by_period.get(period, [])
            if len(tps) >= 2:
                pairs.append((tps[0], tps[-1]))

        # End-to-end: first BoSY → last EoSY
        first_bosy = by_period.get("BoSY", [None])[0]
        last_eosy = by_period.get("EoSY", [None])[-1]
        if first_bosy and last_eosy and first_bosy[0] != last_eosy[0]:
            pairs.append((first_bosy, last_eosy))

    return pairs


def compute_chain_progress(
    performance,
    raw_data,
    validation,
    time_chain=None,
    school_year_chains=None,
    count_threshold=0.25,
    ordinal_sd=None,
    ordinal_skew=None,
):
    """
    Compute within-school-year segment deltas and composite progress.

    Iterates per school year (no cross-year segments). For each school
    year chain, generates segments for consecutive pairs and a spanning
    BoSY→EoSY segment if an intermediate timepoint (MoSY) exists.

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
        Flat list of all timepoints for data loading. Defaults to
        ``ALL_TIMEPOINTS``.
    school_year_chains : dict, optional
        ``{school_year: [(sy, period), ...]}`` defining per-year chains.
        Defaults to ``SCHOOL_YEAR_CHAINS``.
    count_threshold : float, optional
        Maximum acceptable proportional change in total student count
        between adjacent time points.  Default 0.25 (25%).
    ordinal_sd : dict, optional
        ``{(sy, period): Series}`` — ordinal SD.
    ordinal_skew : dict, optional
        ``{(sy, period): Series}`` — ordinal skewness.

    Returns
    -------
    pandas.DataFrame
        One row per school (union of all schools across all time
        points).  Columns include metadata, performance at each time
        point, segment deltas, segment validity flags,
        ``segments_available``, and ``composite_score``.
    """
    if time_chain is None:
        time_chain = ALL_TIMEPOINTS
    if school_year_chains is None:
        school_year_chains = SCHOOL_YEAR_CHAINS

    # ---- Collect all school IDs across all timepoints ----
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
    for key in time_chain:
        sy, period = key
        col = f"perf_{period}_{sy}"
        if key in performance:
            result[col] = performance[key].reindex(idx)
        else:
            result[col] = np.nan

    # ---- SD and Skew at each time point ----
    has_moments = ordinal_sd is not None and ordinal_skew is not None
    if has_moments:
        for key in time_chain:
            sy, period = key
            sd_col = f"sd_{period}_{sy}"
            skew_col = f"skew_{period}_{sy}"
            result[sd_col] = ordinal_sd[key].reindex(idx) if key in ordinal_sd else np.nan
            result[skew_col] = ordinal_skew[key].reindex(idx) if key in ordinal_skew else np.nan

    # ---- Build segment pairs from school-year chains ----
    segment_pairs = _build_segment_pairs(school_year_chains)

    seg_delta_cols = []
    seg_valid_cols = []
    seg_valid_strict_cols = []
    seg_sd_delta_cols = []
    seg_skew_delta_cols = []

    for seg_n, (t0, t1) in enumerate(segment_pairs, start=1):
        label = _segment_label(t0, t1)

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

        # Strict segment validity
        valid_strict_col = f"seg{seg_n}_valid_strict"
        strict0 = (
            validation[t0]["valid_strict"].reindex(idx, fill_value=False)
            if t0 in validation and "valid_strict" in validation[t0].columns
            else pd.Series(False, index=idx)
        )
        strict1 = (
            validation[t1]["valid_strict"].reindex(idx, fill_value=False)
            if t1 in validation and "valid_strict" in validation[t1].columns
            else pd.Series(False, index=idx)
        )
        result[valid_strict_col] = strict0 & strict1 & count_stable
        seg_valid_strict_cols.append(valid_strict_col)

        seg_delta_cols.append(delta_col)
        seg_valid_cols.append(valid_col)

        if has_moments:
            sd_delta_col = f"seg{seg_n}_{label}_sd_delta"
            skew_delta_col = f"seg{seg_n}_{label}_skew_delta"

            sd0 = ordinal_sd[t0].reindex(idx) if t0 in ordinal_sd else pd.Series(np.nan, index=idx)
            sd1 = ordinal_sd[t1].reindex(idx) if t1 in ordinal_sd else pd.Series(np.nan, index=idx)
            sd_delta = sd1 - sd0
            sd_delta[~seg_valid] = np.nan
            result[sd_delta_col] = sd_delta
            seg_sd_delta_cols.append(sd_delta_col)

            skew0 = ordinal_skew[t0].reindex(idx) if t0 in ordinal_skew else pd.Series(np.nan, index=idx)
            skew1 = ordinal_skew[t1].reindex(idx) if t1 in ordinal_skew else pd.Series(np.nan, index=idx)
            skew_delta = skew1 - skew0
            skew_delta[~seg_valid] = np.nan
            result[skew_delta_col] = skew_delta
            seg_skew_delta_cols.append(skew_delta_col)

    # ---- Summary ----
    result["segments_available"] = result[seg_valid_cols].sum(axis=1)
    if seg_valid_strict_cols:
        result["segments_available_strict"] = result[seg_valid_strict_cols].sum(axis=1)

    # Composite: sum of Learning (full-year) segment deltas only
    learning_delta_cols = [c for c in seg_delta_cols if "Learning_" in c]
    result["composite_score"] = result[learning_delta_cols].sum(
        axis=1, min_count=1
    )

    if has_moments:
        learning_sd_cols = [c for c in seg_sd_delta_cols if "Learning_" in c]
        learning_skew_cols = [c for c in seg_skew_delta_cols if "Learning_" in c]
        result["composite_sd_delta"] = result[learning_sd_cols].sum(
            axis=1, min_count=1
        )
        result["composite_skew_delta"] = result[learning_skew_cols].sum(
            axis=1, min_count=1
        )

    # ---- Print summary ----
    n_total = len(result)
    for i, col in enumerate(seg_delta_cols):
        n_valid = result[seg_valid_cols[i]].sum()
        n_strict = result[seg_valid_strict_cols[i]].sum() if seg_valid_strict_cols else 0
        mean_delta = result[col].mean()
        print(
            f"Segment {i+1} ({col}): "
            f"{n_valid}/{n_total} valid, "
            f"{n_strict}/{n_total} valid_strict, "
            f"mean delta = {mean_delta:.4f}"
        )

    # Learning segments summary
    learning_valid_cols = [seg_valid_cols[i] for i, c in enumerate(seg_delta_cols) if "Learning_" in c]
    learning_strict_cols = [seg_valid_strict_cols[i] for i, c in enumerate(seg_delta_cols) if "Learning_" in c]
    full_learning = result[learning_valid_cols].all(axis=1) if learning_valid_cols else pd.Series(False, index=idx)
    full_learning_strict = result[learning_strict_cols].all(axis=1) if learning_strict_cols else pd.Series(False, index=idx)
    print(
        f"\nBoth Learning segments valid: "
        f"{full_learning.sum()}/{n_total} schools, "
        f"{full_learning_strict.sum()}/{n_total} strict"
    )
    composite_valid = result["composite_score"].notna()
    print(
        f"Composite score (Learning segments): {composite_valid.sum()} schools scored, "
        f"mean = {result['composite_score'].mean():.4f}"
    )

    return result
