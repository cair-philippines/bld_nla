"""
Prepare pre-computed parquet files for the CRLA dashboard.

Reads raw assessment CSVs via the pipeline modules and produces:
  - school_metadata.parquet   (one row per school)
  - school_profiles.parquet   (long format for charting)
  - school_ordinal.parquet    (ordinal scores per school x timepoint)

Usage:
    python scripts/prepare_data.py   (from dashboard/ directory)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add modules to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "modules"))

from preprocessing import (
    load_all_assessments,
    compute_percentages,
    validate_timepoint,
    _clean_raw_to_numeric,
    READING_PROFILES,
    GRADE_LANGUAGE_GROUPS,
    CANONICAL_GRADE_COLUMNS,
    METADATA_COLUMNS,
    _get_group_columns,
    get_total_assessed,
)
from analysis import (
    ORDINAL_WEIGHTS,
    ALL_TIMEPOINTS,
    SCHOOL_YEAR_CHAINS,
    TIME_CHAIN,
    _build_segment_pairs,
    _segment_label,
    process_all_timepoints,
    compute_chain_progress,
)
from preprocessing import resolve_latest_exports
from lgu_matching import (
    load_deped_psgc,
    load_lgu_revenue,
    build_school_lgu_crosswalk,
    match_lgu_revenue,
)
from priority_ranking import compute_priority_ranking

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Bronze layer is the canonical source (data/bronze/crla/).
# resolve_latest_exports() scans for the most recent file per timepoint.
LOCAL_FILES = resolve_latest_exports()

TIMEPOINT_ORDER = ALL_TIMEPOINTS

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"

ORDINAL_VALUES = list(ORDINAL_WEIGHTS.values())  # [1, 2, 3, 4, 5]

PROFILE_ORDER = {p: i + 1 for i, p in enumerate(READING_PROFILES)}

GRADE_LANG_LABELS = []
for grade, lang in GRADE_LANGUAGE_GROUPS:
    GRADE_LANG_LABELS.append(f"{grade} {lang}" if lang else grade)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_numeric(series):
    """Convert a series to numeric, handling commas and strings."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )


def _timepoint_label(sy, period):
    return f"{period} {sy}"


# ---------------------------------------------------------------------------
# Build school_metadata
# ---------------------------------------------------------------------------

def build_metadata(df_all):
    """One row per school with metadata and available timepoints."""
    rows = {}
    for key in TIMEPOINT_ORDER:
        if key not in df_all:
            continue
        sy, period = key
        label = _timepoint_label(sy, period)
        df = df_all[key]
        src = df.copy()
        if "School ID" in src.columns:
            src = src.set_index("School ID")

        for sid in src.index:
            if sid not in rows:
                rows[sid] = {
                    "School ID": sid,
                    "School Name": src.at[sid, "School Name"]
                    if "School Name" in src.columns
                    else np.nan,
                    "Region": src.at[sid, "Region"]
                    if "Region" in src.columns
                    else np.nan,
                    "Division": src.at[sid, "Division"]
                    if "Division" in src.columns
                    else np.nan,
                    "District": src.at[sid, "District"]
                    if "District" in src.columns
                    else np.nan,
                    "_timepoints": [],
                }
            rows[sid]["_timepoints"].append(label)
            # Fill missing metadata from later timepoints
            for col in METADATA_COLUMNS:
                if pd.isna(rows[sid].get(col)) and col in src.columns:
                    rows[sid][col] = src.at[sid, col]

    result = pd.DataFrame(rows.values())
    result["timepoints_available"] = result["_timepoints"].apply(
        lambda x: ", ".join(x)
    )
    result = result.drop(columns=["_timepoints"])
    return result


# ---------------------------------------------------------------------------
# Build school_profiles (long format)
# ---------------------------------------------------------------------------

def build_profiles(df_all, percentages):
    """Long-format: school x timepoint x grade-language x profile."""
    records = []

    for key in TIMEPOINT_ORDER:
        if key not in df_all:
            continue
        sy, period = key
        label = _timepoint_label(sy, period)

        raw_df = df_all[key].copy()
        if "School ID" in raw_df.columns:
            raw_df = raw_df.set_index("School ID")

        pct_df = percentages[key]

        for gi, (grade, lang) in enumerate(GRADE_LANGUAGE_GROUPS):
            cols = _get_group_columns(grade, lang)
            gl_label = GRADE_LANG_LABELS[gi]

            for pi, (col, profile) in enumerate(zip(cols, READING_PROFILES)):
                raw_vals = _clean_numeric(raw_df[col]) if col in raw_df.columns else pd.Series(np.nan, index=raw_df.index)
                pct_vals = pct_df[col] if col in pct_df.columns else pd.Series(np.nan, index=pct_df.index)

                # Group total = sum of raw counts for all 5 profiles in this group
                group_raw = pd.DataFrame({
                    c: _clean_numeric(raw_df[c]) for c in cols if c in raw_df.columns
                })
                group_totals = group_raw.sum(axis=1)

                for sid in raw_df.index:
                    records.append({
                        "School ID": sid,
                        "school_year": sy,
                        "period": period,
                        "timepoint_label": label,
                        "grade": grade,
                        "language": lang if lang else "",
                        "grade_lang": gl_label,
                        "profile": profile,
                        "profile_order": pi + 1,
                        "raw_count": raw_vals.get(sid, np.nan),
                        "percentage": pct_vals.get(sid, np.nan),
                        "group_total": group_totals.get(sid, np.nan),
                    })

    df = pd.DataFrame(records)
    # Clean types
    for col in ["raw_count", "group_total"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["percentage"] = pd.to_numeric(df["percentage"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Build school_ordinal
# ---------------------------------------------------------------------------

def build_ordinal(df_all, percentages, validation):
    """Ordinal scores per school x timepoint at multiple aggregation levels."""
    records = []

    for key in TIMEPOINT_ORDER:
        if key not in df_all:
            continue
        sy, period = key
        label = _timepoint_label(sy, period)

        raw_df = df_all[key].copy()
        if "School ID" in raw_df.columns:
            raw_df = raw_df.set_index("School ID")

        pct_df = percentages[key]
        val_df = validation[key]

        # Total assessed per school (unique students, from cached grade totals)
        total_assessed = get_total_assessed(sy, period).reindex(pct_df.index)

        # Ordinal score and GL% per grade-language group
        group_scores = {}
        group_gl_pcts = {}
        for gi, (grade, lang) in enumerate(GRADE_LANGUAGE_GROUPS):
            cols = _get_group_columns(grade, lang)
            gl_label = GRADE_LANG_LABELS[gi]
            group_data = pct_df[cols]
            has_data = group_data.notna().all(axis=1)

            score = sum(
                group_data[col] * w for col, w in zip(cols, ORDINAL_VALUES)
            ) / 100
            score[~has_data] = np.nan
            group_scores[gl_label] = score

            # GL% is the last column (Grade Level) in each group
            gl_pct = group_data[cols[-1]].copy()
            gl_pct[~has_data] = np.nan
            group_gl_pcts[gl_label] = gl_pct

        # Grade-level aggregations
        ordinal_G1 = group_scores["G1"]
        ordinal_G2 = pd.concat(
            [group_scores["G2 MT"], group_scores["G2 Fil"]], axis=1
        ).mean(axis=1)
        ordinal_G3 = pd.concat(
            [group_scores["G3 MT"], group_scores["G3 Fil"], group_scores["G3 Eng"]],
            axis=1,
        ).mean(axis=1)
        ordinal_overall = pd.concat(
            list(group_scores.values()), axis=1
        ).mean(axis=1)

        # Average GL% across grade-language groups
        pct_gl_overall = pd.concat(
            list(group_gl_pcts.values()), axis=1
        ).mean(axis=1)

        for sid in pct_df.index:
            rec = {
                "School ID": sid,
                "school_year": sy,
                "period": period,
                "timepoint_label": label,
                "total_assessed": total_assessed.get(sid, np.nan),
                "ordinal_overall": ordinal_overall.get(sid, np.nan),
                "ordinal_G1": ordinal_G1.get(sid, np.nan),
                "ordinal_G2": ordinal_G2.get(sid, np.nan),
                "ordinal_G3": ordinal_G3.get(sid, np.nan),
                "pct_gl": pct_gl_overall.get(sid, np.nan),
                "valid": val_df.at[sid, "valid"] if sid in val_df.index else False,
            }
            for gl_label, score_series in group_scores.items():
                col_name = f"ordinal_{gl_label.replace(' ', '_')}"
                rec[col_name] = score_series.get(sid, np.nan)
            records.append(rec)

    df = pd.DataFrame(records)

    # Append national means as synthetic school
    nat_rows = []
    for key in TIMEPOINT_ORDER:
        if key not in percentages:
            continue
        sy, period = key
        label = _timepoint_label(sy, period)
        tp_data = df[(df["school_year"] == sy) & (df["period"] == period) & df["valid"]]

        nat = {
            "School ID": -1,
            "school_year": sy,
            "period": period,
            "timepoint_label": label,
            "total_assessed": tp_data["total_assessed"].sum(),
            "ordinal_overall": tp_data["ordinal_overall"].mean(),
            "pct_gl": tp_data["pct_gl"].mean(),
            "ordinal_G1": tp_data["ordinal_G1"].mean(),
            "ordinal_G2": tp_data["ordinal_G2"].mean(),
            "ordinal_G3": tp_data["ordinal_G3"].mean(),
            "valid": True,
        }
        for gl_label in GRADE_LANG_LABELS:
            col_name = f"ordinal_{gl_label.replace(' ', '_')}"
            nat[col_name] = tp_data[col_name].mean()
        nat_rows.append(nat)

    df = pd.concat([df, pd.DataFrame(nat_rows)], ignore_index=True)
    return df


# ---------------------------------------------------------------------------
# Build school_priority
# ---------------------------------------------------------------------------

# External data paths (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PSGC_PATH = PROJECT_ROOT / "data/raw/SY 2024-2025 School Level Database WITH PSGC.xlsx"
BLGF_PATH = PROJECT_ROOT / "data/raw/By-LGU-SRE-2024.xlsx"
ENROLLMENT_PATH = PROJECT_ROOT / "data/raw/public_project_bukas_enrollment_2024-25.csv"


def build_priority(df_all):
    """Priority ranking per school x segment with three-pillar percentiles.

    Runs the full pipeline (ordinal moments → chain progress → priority
    ranking) and returns a DataFrame with one row per school per segment.
    """
    results = process_all_timepoints(df_all, scoring="ordinal")
    progress_df = compute_chain_progress(
        performance=results["performance"],
        raw_data=df_all,
        validation=results["validation"],
        ordinal_sd=results.get("ordinal_sd"),
        ordinal_skew=results.get("ordinal_skew"),
    )

    # LGU matching
    psgc_df = load_deped_psgc(str(PSGC_PATH))
    crosswalk_df = build_school_lgu_crosswalk(psgc_df)
    lgu_revenue_df = load_lgu_revenue(str(BLGF_PATH))
    matched_lgu_df, _, _ = match_lgu_revenue(crosswalk_df, lgu_revenue_df)

    # Enrollment for per-capita SEF
    enroll = pd.read_csv(str(ENROLLMENT_PATH))
    grade_cols = [c for c in enroll.columns if c.endswith("_male") or c.endswith("_female")]
    enroll["total_enrolled"] = enroll[grade_cols].sum(axis=1)

    segment_pairs = _build_segment_pairs()
    all_segments = []
    for seg_idx, (t_from, t_to) in enumerate(segment_pairs):
        tp_from_label = _timepoint_label(*t_from)
        tp_to_label = _timepoint_label(*t_to)

        ranking_df, summary = compute_priority_ranking(
            progress_df, seg_idx,
            crosswalk_df=crosswalk_df,
            matched_lgu_df=matched_lgu_df,
            enrollment_df=enroll,
        )

        seg = pd.DataFrame({
            "School ID": ranking_df.index,
            "tp_from": tp_from_label,
            "tp_to": tp_to_label,
            "segment_label": _segment_label(t_from, t_to),
            "need_pctile": ranking_df["need_pctile"].values,
            "impact_pctile": ranking_df["impact_pctile"].values,
            "capacity_gap_pctile": ranking_df["capacity_gap_pctile"].values,
            "priority_score": ranking_df["priority_score"].values,
            "priority_pctile": ranking_df["priority_pctile"].values,
            "lgu_name": ranking_df["lgu_name"].values,
            "sef_per_capita": ranking_df["sef_per_capita"].values,
        })
        all_segments.append(seg)

    return pd.concat(all_segments, ignore_index=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading raw data ...")
    df_all = load_all_assessments(file_map=LOCAL_FILES, source="local")

    print("Computing percentages and validation ...")
    percentages = {}
    validation = {}
    for key, df in df_all.items():
        percentages[key] = compute_percentages(df)
        validation[key] = validate_timepoint(
            percentages[key],
            raw_counts_df=_clean_raw_to_numeric(df),
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Building school_metadata ...")
    meta = build_metadata(df_all)
    meta.to_parquet(OUTPUT_DIR / "school_metadata.parquet", index=False)
    print(f"  → {len(meta)} schools")

    print("Building school_profiles ...")
    profiles = build_profiles(df_all, percentages)
    profiles.to_parquet(OUTPUT_DIR / "school_profiles.parquet", index=False)
    print(f"  → {len(profiles)} rows")

    print("Building school_ordinal ...")
    ordinal = build_ordinal(df_all, percentages, validation)
    ordinal.to_parquet(OUTPUT_DIR / "school_ordinal.parquet", index=False)
    print(f"  → {len(ordinal)} rows")

    print("Building school_priority ...")
    priority = build_priority(df_all)
    priority.to_parquet(OUTPUT_DIR / "school_priority.parquet", index=False)
    print(f"  → {len(priority)} rows ({priority['segment_label'].nunique()} segments)")

    print(f"\nAll files written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
