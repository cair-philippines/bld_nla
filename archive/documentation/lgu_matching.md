# LGU Matching and School-to-LGU Crosswalk

## Overview

The LGU matching module bridges school-level CRLA data to municipality/city-level external datasets (e.g., LGU revenue). It produces a **reusable crosswalk** — a stable mapping from School ID to PSGC municipality/city code — so that any future LGU-level dataset can be joined to schools without re-matching 39K records.

## Data Sources

| Source | File | Purpose |
|--------|------|---------|
| DepEd PSGC School Database | `SY 2024-2025 School Level Database WITH PSGC.xlsx` | Maps School ID → PSGC municipality/city code and name |
| DOF BLGF Statement of Receipts and Expenditures | `By-LGU-SRE-2024.xlsx` | LGU-level revenue and expenditure data (cities, municipalities, provinces) |
| CRLA pipeline output | Step 1 harmonized data | School IDs to be enriched |

### DepEd PSGC Database Schema

Excel file with sheet `DB`. Header at row 6, data from row 7. Key columns:

| Raw Column | Renamed To | Description |
|------------|-----------|-------------|
| `BEIS School ID` | `School ID` | Unique school identifier |
| `(PSGC) REGION NAME` | `psgc_region` | Full region name (e.g., "Region I (Ilocos Region)") |
| `(PSGC) PROVINCE NAME` | `psgc_province` | Province or independent city name |
| `(PSGC) MUNCIPAL/CITY` | `psgc_muni_code` | PSGC numeric code for the municipality/city |
| `(PSGC) MUNCIPAL/CITY NAME` | `psgc_muni_name` | Municipality/city name |

### DOF BLGF Revenue Schema

Excel file with sheet `By LGU SRE 2024`. Multi-header layout, data from row 11. Columns are selected by **positional index** (not by name) due to merged header cells. The module maps 26 columns covering:

- Geographic identifiers (region, province, LGU name, LGU type)
- Real Property Tax (general fund, special education fund, total)
- Tax revenue (business, other, total)
- Non-tax revenue (regulatory fees, service charges, economic enterprises, other receipts, total)
- Local and external source totals
- National Tax Allotment (IRA)
- Selected expenditure items (education/culture/sports, total social services, total operating)

Full column mapping is defined in `LGU_REVENUE_COLS` in `modules/lgu_matching.py`.

## Name Normalization

Three data sources use different conventions for the same geographic entities. The module normalizes all names before matching.

### Region Normalization

| Source | Example | Canonical Form |
|--------|---------|---------------|
| PSGC | `Region I (Ilocos Region)` | `Region I` |
| BLGF | `Region I` | `Region I` |
| BLGF | `CARAGA` | `Region XIII` |
| PSGC | `Cordillera Administrative Region (CAR)` | `CAR` |
| PSGC | `Negros Island Region (NIR)` | `NIR` |

### Municipality/City Name Normalization

Applied to province and municipality/city names:

1. Lowercase and strip whitespace
2. Replace `ñ`, `¤`, `ã±` with `n` (handles encoding variants)
3. Remove parenthetical suffixes (e.g., `"Caloocan (Capital)"` → `"caloocan"`)
4. Strip prefixes: `"city of "`, `"municipality of "`
5. Strip trailing `" city"`

Example: `"City of Mandaluyong (Capital)"` → `"mandaluyong"`

## Matching Strategy

The module matches LGU revenue records (cities and municipalities only, not provinces) to the crosswalk using a **cascading multi-pass strategy**. Each pass catches a specific class of mismatches.

### Pass 1 — Exact Match (region + province + name)

Standard case. Normalized region, province, and municipality name must all match exactly. Handles the majority of LGUs.

### Pass 2 — Cross-Region Exact Match (province + name only)

Ignores region, matches on province and name. This resolves the **NIR administrative boundary mismatch**: the Negros Island Region (NIR) was created from parts of Region VI (Western Visayas) and Region VII (Central Visayas). The BLGF data uses NIR, while the PSGC database still uses the original regional assignment.

### Pass 3 — Independent City Match

Handles cities where the PSGC database lists the city as both the province and the municipality (e.g., `province="City of Manila"`, `muni="City of Manila"`), while the BLGF data lists a different province (e.g., `province="Metro Manila"`). Tries:

1. Municipality name matches AND province name matches municipality name
2. Municipality name is unique across all provinces

### Pass 4 — Fuzzy Match (cascading scope)

For remaining unmatched LGUs, uses `SequenceMatcher` string similarity with a configurable threshold (default 0.80). Cascades through narrowing scopes to minimize false matches:

1. **Region + Province**: candidates from the same region and province
2. **Province only**: candidates from the same province (any region)
3. **Region only**: candidates from the same region (any province)

The first scope that produces a match above the threshold is accepted.

### Unmatched LGUs

Three LGUs remain unmatched (of 1,634 total cities/municipalities):

| LGU | Province | Reason |
|-----|----------|--------|
| City of Manila | Metro Manila | PSGC splits Manila into sub-districts (Tondo, Sampaloc, Intramuros, etc.) with no single unified entry. Handled via province-level fallback during school join. |
| Bacungan | Palawan | Not present in the PSGC school database (no schools in this municipality). |
| Datu Montawal | Maguindanao | Not present in the PSGC school database. |

## School-to-Revenue Join

`join_revenue_to_schools()` connects individual schools to their LGU's revenue data via a **two-pass join**:

1. **Primary**: Join on `psgc_muni_code` (covers 98%+ of schools)
2. **Fallback**: For schools with no muni-code match, join on normalized province name. This handles Manila schools (PSGC uses sub-district codes that don't appear in the BLGF data) and similar edge cases.

Default revenue columns joined to each school:

| Column | Description |
|--------|-------------|
| `rpt_special_education_fund` | Special Education Fund (SEF) — used for Capacity Gap pillar in priority ranking |
| `total_local_sources` | Sum of tax and non-tax locally-generated revenue |
| `total_external_sources` | National transfers + inter-local transfers + extraordinary |
| `total_current_operating_income` | Total income (local + external) |
| `national_tax_allotment` | National Tax Allotment (formerly IRA) |
| `expenditure_education_culture_sports` | LGU spending on education, culture, and sports |
| `total_current_operating_expenditure` | Total LGU operating expenditure |

## Coverage Results

| Metric | Value |
|--------|-------|
| BLGF cities/municipalities | 1,634 |
| Matched to PSGC crosswalk | 1,631 (99.8%) |
| Unmatched | 3 |
| CRLA schools in crosswalk | 39,206 |
| Schools with LGU revenue data | 38,811 (99.0%) |

### Match Type Breakdown

| Match Type | Count |
|------------|-------|
| `exact` | ~1,540 |
| `exact_cross_region` | ~55 (NIR municipalities) |
| `independent_city` | ~25 |
| `fuzzy_region+province` | ~10 |
| `fuzzy_province_only` | ~1 |
| `unmatched` | 3 |

## Output Files

All saved to `data/modified/`:

| File | Description |
|------|-------------|
| `school_lgu_crosswalk.parquet` | 60,094 rows — School ID to PSGC municipality code mapping with normalized names |
| `lgu_revenue_matched.parquet` | 1,631 rows — LGU revenue records with matched PSGC codes |
| `lgu_match_log.csv` | 1,634 rows — audit trail showing match type, similarity score, and matched entity for each LGU |

## Reusability

The crosswalk is designed as a **stable bridge**. To add a new LGU-level dataset:

1. Load and normalize its region/province/LGU names using `normalize_region()` and `normalize_name()`.
2. Match to the crosswalk using `match_lgu_revenue()` (or a similar function adapted for the new dataset's structure).
3. Join to schools via `join_revenue_to_schools()` using the matched `psgc_muni_code`.

The crosswalk itself does not need to be rebuilt unless the school universe changes (e.g., a new PSGC database release).

## Module Reference

All functions are in `modules/lgu_matching.py`:

| Function | Purpose |
|----------|---------|
| `load_deped_psgc(filepath)` | Parse DepEd PSGC Excel into clean DataFrame |
| `load_lgu_revenue(filepath)` | Parse DOF BLGF Excel into clean DataFrame |
| `normalize_region(name)` | Map region name variants to canonical form |
| `normalize_name(name)` | Normalize province/municipality names for matching |
| `build_school_lgu_crosswalk(psgc_df)` | Add normalized columns to PSGC data for matching |
| `match_lgu_revenue(crosswalk_df, lgu_revenue_df, threshold)` | Multi-pass LGU matching with audit log |
| `join_revenue_to_schools(crosswalk_df, matched_lgu_df, revenue_cols)` | Two-pass join of LGU data to individual schools |
