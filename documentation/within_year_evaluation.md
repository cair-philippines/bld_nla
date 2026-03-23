# Within-School-Year Evaluation Workflow

## Context

Stakeholders prefer evaluating school performance by **within-school-year segments only** — comparing BoSY to EoSY within the same school year. The cross-year "Retention" segment (EoSY → next BoSY) conflates summer learning loss, new-cohort effects, and school performance, making it difficult to attribute outcomes to schools.

With the arrival of EoSY 2025-26 data, the pipeline transitions to this within-year model.

## New Data Sources

Five CRLA datasets exported via automated Looker Studio scraper (`notebooks/0.2-export_data_from_crla_dashboard.ipynb`):

| File | Timepoint | Schools | Schema |
|------|-----------|---------|--------|
| `CRLA_BoSY_2024-25_*.csv` | BoSY 2024-25 | 35,280 | 50 cols (Type A) |
| `CRLA_EoSY_2024-25_*.csv` | EoSY 2024-25 | 37,045 | 50 cols (Type A) |
| `CRLA_BoSY_2025-26_*.csv` | BoSY 2025-26 | 38,981 | 53 cols (Type B) |
| `CRLA_MoSY_2025-26_*.csv` | MoSY 2025-26 | 38,297 | 47 cols (Type C) |
| `CRLA_EoSY_2025-26_*.csv` | EoSY 2025-26 | 38,322 | 53 cols (Type B) |

Location: `data/raw/dashboard_export/`

### Schema Variants

- **Type A** (SY 2024-25 archive): 50 columns. Combined `G2 Total Assessed` / `G3 Total Assessed`.
- **Type B** (SY 2025-26 national dashboard): 53 columns. Separate per-language totals: `G2 Total MT Assessed`, `G2 Total Fil Assessed`, `G3 Total MT Assessed`, etc.
- **Type C** (MoSY 2025-26): 47 columns. Same as Type B but **missing G3 MT entirely** (only 5 of 6 grade-language groups). This is expected — MoSY is a targeted mid-year assessment for a subset of schools.

### Data Format Difference

Dashboard exports use **decimals** (0.386) for percentages and **raw integers** (2814) for counts. The original pipeline files use **percentage strings** ("38.59%") and **comma-separated quoted strings** ("2,814"). The harmonization step must detect and normalize both formats.

## New Segment Structure

### Previous (retired)

```
BoSY 2024-25 → EoSY 2024-25 → BoSY 2025-26
     seg1 (Learning_2024-25)   seg2 (Retention_2024-25_to_2025-26)
```

The Retention segment is **removed entirely**.

### Current

Per-school-year chains with no cross-year segments:

```
SY 2024-25:  BoSY ────────────────────── EoSY
                  Learning_2024-25

SY 2025-26:  BoSY ──── MoSY ──── EoSY
                  BoSYMoSY  MoSYEoSY
                  └── Learning_2025-26 ──┘
```

| Segment Label | Pair | Scope |
|---------------|------|-------|
| `Learning_2024-25` | BoSY → EoSY 2024-25 | All schools with data at both endpoints |
| `Learning_2025-26` | BoSY → EoSY 2025-26 | All schools with data at both endpoints |
| `BoSYMoSY_2025-26` | BoSY → MoSY 2025-26 | **Intervention subset only** (schools with MoSY data) |
| `MoSYEoSY_2025-26` | MoSY → EoSY 2025-26 | **Intervention subset only** (schools with MoSY data) |

### MoSY as Optional Intermediate

MoSY is **not a universal assessment**. Only schools subject to a specific literacy intervention participated. Therefore:
- MoSY segments (`BoSYMoSY`, `MoSYEoSY`) are NaN for non-intervention schools
- The full-year `Learning` segment is always computed (BoSY → EoSY) regardless of MoSY availability
- MoSY missing G3 MT is handled by existing validation (school still has 5 of 6 groups — passes `has_all_grades` since G3 Fil/Eng are present)

## Priority Ranking Configuration

Two ranking modes:

1. **Latest full-year**: Priority ranking on `Learning_2025-26` (BoSY → EoSY 2025-26). This is the primary ranking for intervention targeting.
2. **Composite across school years**: Combines within-year deltas from both `Learning_2024-25` and `Learning_2025-26`. Schools must have valid data in both years.

The three-pillar formula (Need × Impact × Capacity Gap) is unchanged.

## Cycle 2 List

The 2nd cycle priority school list will be **regenerated** based on the within-school-year segments (not the retired Retention segment). The existing `output/priority_schools_cycle2_retention.xlsx` becomes a historical artifact.

## Implementation Phases

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Data ingestion: format detection, MoSY schema, new file map | **Done** |
| 2 | Time chain restructuring: SCHOOL_YEAR_CHAINS, segment labels, chain progress | **Done** |
| 3 | Priority ranking: segment selection by (SY, label) | **Done** |
| 4 | Output & dashboard data regeneration | **Done** |
| 5 | Notebooks: re-execute with new data and segments | Deferred |

## Results (Phases 1–4)

| Segment | Strict-Valid | Ranked | Mean Delta |
|---------|-------------|--------|------------|
| Learning_2024-25 | 22,206 | 22,114 | +0.82 |
| BoSYMoSY_2025-26 | 9,061 | 8,996 | +0.56 |
| MoSYEoSY_2025-26 | 9,722 | 9,652 | +0.56 |
| Learning_2025-26 | 19,605 | 19,441 | +1.10 |

- Total schools (union): 39,438
- Both Learning segments valid: 28,560 (16,824 strict)
- Composite score (Learning segments): 37,509 schools, mean +1.67
- EoSY 2025-26 national mean: 4.15 (vs 4.13 in EoSY 2024-25)
- Old `Retention_2024-25_to_2025-26.csv` removed from output/
- Composite ranking: `output/priority_ranking_composite.xlsx` (16,765 ranked, 131 1st-cycle tagged)
- Build script: `scripts/build_composite_ranking.py` (permanent, rerunnable)

## Technical Notes

### Pipeline Changes (Phases 1–4)

**preprocessing.py**:
- Add format detection: decimal vs percentage strings, raw vs comma-separated counts
- Handle MoSY 47-column schema (G3 MT missing → NaN)
- New `resolve_latest_export()` helper to find most recent dashboard export per timepoint
- New file map entries for MoSY 2025-26 and EoSY 2025-26

**analysis.py**:
- Replace flat `TIME_CHAIN` with `SCHOOL_YEAR_CHAINS` dict
- Keep flat `ALL_TIMEPOINTS` (union) for data loading
- Update `_segment_label()` for BoSYMoSY / MoSYEoSY labels
- Update `compute_chain_progress()` to iterate per school year, generate spanning BoSY→EoSY segment alongside intermediate MoSY segments

**priority_ranking.py**:
- Accept segment by (school_year, label) or maintain segment_idx within a given school year
- No formula changes

**output.py / dashboard/prepare_data.py**:
- Update timepoint lists and segment loops
- Remove Retention segment references
