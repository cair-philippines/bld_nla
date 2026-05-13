"""
Build the gold layer for RMA.

Reads RMA silver parquets and computes school-level analytical indicators.
Three key stages are processed independently:
  KS1 (G1–G3): 3 timepoints (EoSY 2024-25, BoSY/EoSY 2025-26), 1 segment
  KS2 (G4–G6): 2 timepoints (BoSY/EoSY 2025-26), 1 segment
  KS3 (G7–G10): 2 timepoints (BoSY/EoSY 2025-26), 1 segment

Note: KS1 BoSY 2024-25 is excluded — School IDs were not populated in that
archive export. No YoY file is produced as a result.

Gold outputs (data/gold/):
  rma_ks{1,2,3}_school_timepoints.parquet  — one row per school × timepoint
  rma_ks{1,2,3}_school_segments.parquet    — one row per school × segment

Usage:
    python scripts/build_gold_rma.py

Prerequisites:
    Run scripts/build_silver.py --rma first.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "modules"))

from rma_preprocessing import (
    SILVER_RMA_DIR,
    RMA_METADATA_COLUMNS,
    RMA_GRADES_BY_KS,
    RMA_TIMEPOINTS_BY_KS,
    get_rma_group_columns,
    compute_rma_percentages,
    compute_rma_ordinal_moments,
    compute_rma_emd,
)

GOLD_DIR = PROJECT_ROOT / "data" / "gold"
AGLHP_LEVEL = "At Grade Level - Highly Proficient"


# ---------------------------------------------------------------------------
# Silver loader
# ---------------------------------------------------------------------------

def load_silver_rma(ks, silver_dir=None):
    """
    Load all available RMA silver parquets for a key stage.

    Returns
    -------
    dict
        {(school_year, period): DataFrame} indexed by School ID.
    """
    if silver_dir is None:
        silver_dir = SILVER_RMA_DIR

    silver_path = Path(silver_dir)
    result = {}
    for sy, period in RMA_TIMEPOINTS_BY_KS[ks]:
        fpath = silver_path / f"{ks}_{sy}_{period}.parquet"
        if fpath.exists():
            df = pd.read_parquet(fpath)
            result[(sy, period)] = df
            print(f"  Loaded silver {ks} {sy} {period}: {len(df)} schools")
        else:
            print(f"  ⚠ Silver not found: {fpath}")
    return result


# ---------------------------------------------------------------------------
# Build timepoints
# ---------------------------------------------------------------------------

def build_timepoints(df_all, percentages, ks):
    """
    Build the school × timepoint gold table for one key stage.

    Columns: School ID, ks, school_year, period, timepoint_label,
    total_assessed, groups_with_data, pct_aglhp,
    ordinal_mean, ordinal_sd, ordinal_skew, ordinal_kurt, bimodality_coef,
    School Name, Region, Division, District.
    """
    grades = RMA_GRADES_BY_KS[ks]
    records = []

    for (sy, period), df in df_all.items():
        label = f"{period} {sy}"
        pct_df = percentages[(sy, period)]
        moments = compute_rma_ordinal_moments(pct_df, ks)

        groups_present = []
        aglhp_pcts = []
        for grade in grades:
            cols = get_rma_group_columns(grade)
            has = pct_df[cols].notna().all(axis=1) & (pct_df[cols].sum(axis=1) > 0)
            groups_present.append(has)
            aglhp_pcts.append(pct_df[f"{grade} {AGLHP_LEVEL}"].where(has))

        groups_with_data = pd.concat(groups_present, axis=1).sum(axis=1).astype(int)
        pct_aglhp = pd.concat(aglhp_pcts, axis=1).mean(axis=1)
        total_assessed = df["total_assessed"] if "total_assessed" in df.columns else pd.Series(np.nan, index=df.index)

        for sid in pct_df.index:
            rec = {
                "School ID": sid,
                "ks": ks,
                "school_year": sy,
                "period": period,
                "timepoint_label": label,
                "total_assessed": total_assessed.get(sid, np.nan),
                "groups_with_data": int(groups_with_data.get(sid, 0)),
                "pct_aglhp": pct_aglhp.get(sid, np.nan),
                "ordinal_mean": moments["ordinal_mean"].get(sid, np.nan),
                "ordinal_sd": moments["ordinal_sd"].get(sid, np.nan),
                "ordinal_skew": moments["ordinal_skew"].get(sid, np.nan),
                "ordinal_kurt": moments["ordinal_kurt"].get(sid, np.nan),
                "bimodality_coef": moments["bimodality_coef"].get(sid, np.nan),
            }
            for col in RMA_METADATA_COLUMNS:
                rec[col] = df.at[sid, col] if col in df.columns else np.nan
            records.append(rec)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Build segments
# ---------------------------------------------------------------------------

def build_segments(percentages, ks):
    """
    Build the school × segment gold table.

    One segment per school year (BoSY → EoSY).  Segments are labeled
    Learning_{sy} and indexed chronologically from 0.
    """
    records = []
    school_years = sorted({sy for sy, _ in percentages})

    for seg_idx, sy in enumerate(school_years):
        t0 = (sy, "BoSY")
        t1 = (sy, "EoSY")
        if t0 not in percentages or t1 not in percentages:
            continue

        pct0 = percentages[t0]
        pct1 = percentages[t1]

        m0 = compute_rma_ordinal_moments(pct0, ks)
        m1 = compute_rma_ordinal_moments(pct1, ks)

        delta_mean = m1["ordinal_mean"] - m0["ordinal_mean"]
        delta_sd = m1["ordinal_sd"] - m0["ordinal_sd"]
        delta_skew = m1["ordinal_skew"] - m0["ordinal_skew"]
        emd = compute_rma_emd(pct0, pct1, ks).reindex(pct0.index)

        for sid in pct0.index:
            records.append({
                "School ID": sid,
                "ks": ks,
                "school_year": sy,
                "segment_label": f"Learning_{sy}",
                "seg_idx": seg_idx,
                "tp_from": f"BoSY {sy}",
                "tp_to": f"EoSY {sy}",
                "delta_mean": delta_mean.get(sid, np.nan),
                "delta_sd": delta_sd.get(sid, np.nan),
                "delta_skew": delta_skew.get(sid, np.nan),
                "emd_mean": emd.get(sid, np.nan),
            })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Per-KS pipeline
# ---------------------------------------------------------------------------

def build_ks(ks):
    print(f"\n{'=' * 60}")
    print(f"RMA Gold — {ks.upper()}")
    print("=" * 60)

    print(f"\nLoading silver ...")
    df_all = load_silver_rma(ks)
    if not df_all:
        print(f"No silver files found for {ks}. Run build_silver.py --rma first.")
        return

    print(f"\nComputing percentages ...")
    percentages = {tp: compute_rma_percentages(df, ks) for tp, df in df_all.items()}

    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nBuilding rma_{ks}_school_timepoints ...")
    tp_df = build_timepoints(df_all, percentages, ks)
    tp_out = GOLD_DIR / f"rma_{ks}_school_timepoints.parquet"
    tp_df.to_parquet(tp_out, index=False)
    print(f"  → {tp_out} ({len(tp_df)} rows, "
          f"{tp_df['School ID'].nunique()} schools, "
          f"{tp_df['timepoint_label'].nunique()} timepoints)")

    print(f"\nBuilding rma_{ks}_school_segments ...")
    seg_df = build_segments(percentages, ks)
    seg_out = GOLD_DIR / f"rma_{ks}_school_segments.parquet"
    seg_df.to_parquet(seg_out, index=False)
    print(f"  → {seg_out} ({len(seg_df)} rows, "
          f"{seg_df['School ID'].nunique()} schools, "
          f"{seg_df['segment_label'].nunique()} segments)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    for ks in ["ks1", "ks2", "ks3"]:
        build_ks(ks)
    print(f"\nAll RMA gold files written to {GOLD_DIR}/")


if __name__ == "__main__":
    main()
