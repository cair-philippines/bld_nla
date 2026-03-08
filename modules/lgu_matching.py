"""
LGU Matching Module

Builds a reusable school-to-LGU crosswalk by joining:
  1. CRLA schools (School ID)
  2. DepEd PSGC database (School ID → municipality/city PSGC code + name)
  3. External LGU-level datasets (matched via Region + Province + LGU name)

The crosswalk is the stable bridge — any future LGU-level dataset can join
through it without re-matching 39K schools.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from difflib import SequenceMatcher


# ---------------------------------------------------------------------------
# 1. Load and parse the DepEd PSGC school database
# ---------------------------------------------------------------------------

def load_deped_psgc(filepath):
    """Load the DepEd School Level Database WITH PSGC.

    Returns a DataFrame with one row per school, containing School ID
    and PSGC-based geographic columns (region, province, municipality/city).
    """
    raw = pd.read_excel(filepath, sheet_name="DB", header=None)
    df = raw.iloc[7:].copy()
    df.columns = raw.iloc[6].values

    # Rename for consistency
    df = df.rename(columns={
        "BEIS School ID": "School ID",
        "(PSGC) REGION NAME": "psgc_region",
        "(PSGC) PROVINCE NAME": "psgc_province",
        "(PSGC) MUNCIPAL/CITY": "psgc_muni_code",
        "(PSGC) MUNCIPAL/CITY NAME": "psgc_muni_name",
    })

    df["School ID"] = pd.to_numeric(df["School ID"], errors="coerce")
    df = df.dropna(subset=["School ID"])
    df["School ID"] = df["School ID"].astype(int)

    keep_cols = [
        "School ID", "Region", "Division",
        "psgc_region", "psgc_province", "psgc_muni_code", "psgc_muni_name",
    ]
    return df[keep_cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. Load and parse the DOF BLGF LGU revenue file
# ---------------------------------------------------------------------------

# Column index mapping for the multi-header Excel layout
LGU_REVENUE_COLS = {
    1: "region",
    2: "province",
    3: "lgu_name",
    4: "lgu_type",
    # Revenue (in PHP, not millions despite the header — values are raw)
    5: "rpt_general_fund",
    6: "rpt_special_education_fund",
    7: "rpt_total",
    8: "tax_on_business",
    9: "other_taxes",
    10: "total_tax_revenue",
    11: "nontax_regulatory_fees",
    12: "nontax_service_charges",
    13: "nontax_economic_enterprises",
    14: "nontax_other_receipts",
    15: "total_nontax_revenue",
    16: "total_local_sources",
    17: "national_tax_allotment",
    18: "other_national_tax_shares",
    19: "inter_local_transfers",
    20: "extraordinary_receipts",
    21: "total_external_sources",
    22: "total_current_operating_income",
    24: "expenditure_education_culture_sports",
    29: "total_social_services_expenditure",
    32: "total_current_operating_expenditure",
}


def load_lgu_revenue(filepath):
    """Load the DOF BLGF Statement of Receipts and Expenditures.

    Returns a DataFrame with one row per LGU (province, city, or municipality),
    with revenue and expenditure columns.
    """
    raw = pd.read_excel(filepath, sheet_name="By LGU SRE 2024", header=None)
    df = raw.iloc[11:].copy()

    # Select and rename columns
    df = df[[c for c in LGU_REVENUE_COLS.keys()]].copy()
    df.columns = [LGU_REVENUE_COLS[c] for c in LGU_REVENUE_COLS.keys()]

    # Keep only valid LGU rows
    df = df[df["lgu_type"].isin(["Province", "City", "Municipality"])].copy()

    # Convert revenue columns to numeric
    revenue_cols = [c for c in df.columns if c not in ("region", "province", "lgu_name", "lgu_type")]
    for col in revenue_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. Region name normalization
# ---------------------------------------------------------------------------

# PSGC uses full names, LGU uses short names, CRLA uses yet another variant
_REGION_NORMALIZE = {
    # PSGC format → canonical
    "Region I (Ilocos Region)": "Region I",
    "Region II (Cagayan Valley)": "Region II",
    "Region III (Central Luzon)": "Region III",
    "Region IV-A (CALABARZON)": "Region IV-A",
    "MIMAROPA Region": "MIMAROPA",
    "Region V (Bicol Region)": "Region V",
    "Region VI (Western Visayas)": "Region VI",
    "Region VII (Central Visayas)": "Region VII",
    "Region VIII (Eastern Visayas)": "Region VIII",
    "Region IX (Zamboanga Peninsula)": "Region IX",
    "Region X (Northern Mindanao)": "Region X",
    "Region XI (Davao Region)": "Region XI",
    "Region XII (SOCCSKSARGEN)": "Region XII",
    "Region XIII (Caraga)": "Region XIII",
    "Cordillera Administrative Region (CAR)": "CAR",
    "National Capital Region (NCR)": "NCR",
    "Bangsamoro Autonomous Region In Muslim Mindanao (BARMM)": "BARMM",
    "Negros Island Region (NIR)": "NIR",
    # LGU format (already short, but normalize MIMAROPA)
    "MIMAROPA Region": "MIMAROPA",
    "CARAGA": "Region XIII",
}


def normalize_region(name):
    """Normalize region name to a canonical short form."""
    if pd.isna(name):
        return name
    name = str(name).strip()
    return _REGION_NORMALIZE.get(name, name)


def normalize_name(name):
    """Normalize a province/municipality name for matching."""
    if pd.isna(name):
        return ""
    s = str(name).strip().lower()
    # Common substitutions
    s = s.replace("ñ", "n").replace("¤", "n").replace("ã±", "n")
    # Remove parenthetical suffixes like "(Capital)"
    if "(" in s:
        s = s[:s.index("(")].strip()
    # Strip "city of" / "municipality of" prefixes
    for prefix in ("city of ", "municipality of "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    # Strip trailing "city"
    if s.endswith(" city"):
        s = s[:-5].strip()
    return s.strip()


# ---------------------------------------------------------------------------
# 4. Build the school-to-LGU crosswalk
# ---------------------------------------------------------------------------

def build_school_lgu_crosswalk(psgc_df):
    """Create a crosswalk from School ID to normalized LGU identifiers.

    Input: output of load_deped_psgc()
    Output: DataFrame with School ID, psgc_muni_code, and normalized
            region/province/municipality names for joining to external data.
    """
    xw = psgc_df.copy()
    xw["region_norm"] = xw["psgc_region"].apply(normalize_region)
    xw["province_norm"] = xw["psgc_province"].apply(normalize_name)
    xw["muni_norm"] = xw["psgc_muni_name"].apply(normalize_name)
    return xw


# ---------------------------------------------------------------------------
# 5. Match LGU revenue to the crosswalk
# ---------------------------------------------------------------------------

def _similarity(a, b):
    """String similarity ratio (0-1)."""
    return SequenceMatcher(None, a, b).ratio()


def match_lgu_revenue(crosswalk_df, lgu_revenue_df, similarity_threshold=0.80):
    """Match LGU revenue data to the school crosswalk.

    Strategy:
    1. Normalize region/province/lgu_name in the revenue data.
    2. Build a lookup of unique (region, province, municipality) from the crosswalk.
    3. Exact match on normalized (region, province, name).
    4. Exact match ignoring region (handles NIR vs Region VI/VII mismatch).
    5. Exact match on name where crosswalk province = name (independent cities).
    6. Fuzzy match with cascading scope: region+province → province only → region only.

    Returns:
        matched_df: LGU revenue rows with matched psgc_muni_code
        unmatched_df: LGU revenue rows that could not be matched
        match_log: details of each match (exact vs fuzzy, similarity score)
    """
    # Filter to cities and municipalities only (provinces are a different level)
    lgu_cm = lgu_revenue_df[
        lgu_revenue_df["lgu_type"].isin(["City", "Municipality"])
    ].copy()

    # Normalize LGU revenue names
    lgu_cm["region_norm"] = lgu_cm["region"].apply(normalize_region)
    lgu_cm["province_norm"] = lgu_cm["province"].apply(normalize_name)
    lgu_cm["lgu_norm"] = lgu_cm["lgu_name"].apply(normalize_name)

    # Unique municipalities from crosswalk (deduplicated)
    xw_munis = crosswalk_df.drop_duplicates(
        subset=["region_norm", "province_norm", "muni_norm"]
    )[["region_norm", "province_norm", "muni_norm", "psgc_muni_code", "psgc_muni_name"]].copy()

    def _log_entry(idx, row, match_type, matched_to, code, sim):
        return {
            "lgu_idx": idx,
            "lgu_name": row["lgu_name"],
            "province": row["province"],
            "region": row["region"],
            "match_type": match_type,
            "matched_to": matched_to,
            "psgc_muni_code": code,
            "similarity": sim,
        }

    def _try_exact(r, p, n):
        """Exact match on region + province + name."""
        mask = (
            (xw_munis["region_norm"] == r)
            & (xw_munis["province_norm"] == p)
            & (xw_munis["muni_norm"] == n)
        )
        hits = xw_munis[mask]
        return hits.iloc[0] if len(hits) == 1 else None

    def _try_exact_province_only(p, n):
        """Exact match on province + name, ignoring region.
        Handles NIR vs Region VI/VII mismatch."""
        mask = (xw_munis["province_norm"] == p) & (xw_munis["muni_norm"] == n)
        hits = xw_munis[mask]
        return hits.iloc[0] if len(hits) == 1 else None

    def _try_independent_city(n):
        """Match independent cities where PSGC province = city name.
        E.g., Manila in LGU has province='Metro Manila', but PSGC has
        province='City of Manila' and muni='City of Manila'."""
        mask = (xw_munis["muni_norm"] == n) & (xw_munis["province_norm"] == n)
        hits = xw_munis[mask]
        if len(hits) == 1:
            return hits.iloc[0]
        # Also try just muni name match (unique across all provinces)
        mask2 = xw_munis["muni_norm"] == n
        hits2 = xw_munis[mask2]
        return hits2.iloc[0] if len(hits2) == 1 else None

    def _try_fuzzy(candidates, n):
        """Best fuzzy match from candidates."""
        if len(candidates) == 0:
            return None, 0.0
        sims = candidates["muni_norm"].apply(lambda x: _similarity(n, x))
        best_idx = sims.idxmax()
        return candidates.loc[best_idx], sims.loc[best_idx]

    match_log = []
    matched_codes = {}

    for idx, row in lgu_cm.iterrows():
        r, p, n = row["region_norm"], row["province_norm"], row["lgu_norm"]

        # 1. Exact: region + province + name
        hit = _try_exact(r, p, n)
        if hit is not None:
            matched_codes[idx] = hit["psgc_muni_code"]
            match_log.append(_log_entry(idx, row, "exact", hit["psgc_muni_name"], hit["psgc_muni_code"], 1.0))
            continue

        # 2. Exact: province + name (region mismatch — NIR/Region VI/VII)
        hit = _try_exact_province_only(p, n)
        if hit is not None:
            matched_codes[idx] = hit["psgc_muni_code"]
            match_log.append(_log_entry(idx, row, "exact_cross_region", hit["psgc_muni_name"], hit["psgc_muni_code"], 1.0))
            continue

        # 3. Independent city (province = city name in PSGC)
        hit = _try_independent_city(n)
        if hit is not None:
            matched_codes[idx] = hit["psgc_muni_code"]
            match_log.append(_log_entry(idx, row, "independent_city", hit["psgc_muni_name"], hit["psgc_muni_code"], 1.0))
            continue

        # 4. Fuzzy: try region+province first, then province only, then region only
        for scope, cands in [
            ("region+province", xw_munis[(xw_munis["region_norm"] == r) & (xw_munis["province_norm"] == p)]),
            ("province_only", xw_munis[xw_munis["province_norm"] == p]),
            ("region_only", xw_munis[xw_munis["region_norm"] == r]),
        ]:
            best, sim = _try_fuzzy(cands, n)
            if best is not None and sim >= similarity_threshold:
                matched_codes[idx] = best["psgc_muni_code"]
                match_log.append(_log_entry(idx, row, f"fuzzy_{scope}", best["psgc_muni_name"], best["psgc_muni_code"], sim))
                break
        else:
            # No match found
            best_name = best["psgc_muni_name"] if best is not None else ""
            best_sim = sim if best is not None else 0.0
            match_log.append(_log_entry(idx, row, "unmatched", best_name, None, best_sim))

    # Apply matches
    lgu_cm["psgc_muni_code"] = lgu_cm.index.map(matched_codes)

    matched_df = lgu_cm[lgu_cm["psgc_muni_code"].notna()].copy()
    unmatched_df = lgu_cm[lgu_cm["psgc_muni_code"].isna()].copy()
    log_df = pd.DataFrame(match_log)

    return matched_df, unmatched_df, log_df


# ---------------------------------------------------------------------------
# 6. Join revenue to schools
# ---------------------------------------------------------------------------

def join_revenue_to_schools(crosswalk_df, matched_lgu_df, revenue_cols=None):
    """Join matched LGU revenue data to individual schools via the crosswalk.

    Two-pass join:
    1. Primary: match on psgc_muni_code (covers most schools).
    2. Fallback: for schools with no muni-code match, match on province name.
       This handles Manila (PSGC splits it into sub-districts) and similar cases.

    Returns a DataFrame with one row per school, containing the school's
    geographic info and its LGU's revenue data.
    """
    if revenue_cols is None:
        revenue_cols = [
            "rpt_special_education_fund",
            "total_local_sources",
            "total_external_sources",
            "total_current_operating_income",
            "national_tax_allotment",
            "expenditure_education_culture_sports",
            "total_current_operating_expenditure",
        ]

    lgu_subset = matched_lgu_df[
        ["psgc_muni_code", "lgu_name", "lgu_type", "province_norm"] + revenue_cols
    ].copy()
    lgu_subset = lgu_subset.rename(columns={"lgu_name": "lgu_revenue_name"})

    # Pass 1: join on muni code
    lgu_by_code = lgu_subset.drop(columns=["province_norm"])
    merged = crosswalk_df.merge(lgu_by_code, on="psgc_muni_code", how="left")

    # Pass 2: fallback on province name for unmatched schools
    missing_mask = merged["lgu_revenue_name"].isna()
    if missing_mask.any():
        lgu_by_province = lgu_subset.drop(columns=["psgc_muni_code"]).drop_duplicates(
            subset=["province_norm"]
        )
        fallback_cols = ["lgu_revenue_name", "lgu_type"] + revenue_cols
        fallback = merged.loc[missing_mask, ["province_norm"]].merge(
            lgu_by_province[["province_norm"] + fallback_cols],
            on="province_norm",
            how="left",
        )
        for col in fallback_cols:
            merged.loc[missing_mask, col] = fallback[col].values

    return merged
