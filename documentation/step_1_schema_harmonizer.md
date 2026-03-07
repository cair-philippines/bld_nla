# Step 1 — Schema Harmonizer

Reference: `documentation/multi_year_expansion_plan.md`

## Objective
Normalize raw CRLA CSVs from different school years into an identical column schema so downstream code is year-agnostic.

## Files Modified/Created

| File | Status | Description |
|---|---|---|
| `modules/gcs_utils.py` | Modified | Added `CSDATA_RAW_DIR`, `CSDATA_MODIFIED_DIR`; fixed `PROJECT_DIR` to use `__file__` instead of `cwd()` |
| `modules/preprocessing.py` | Created | `harmonize_columns()`, `load_assessment_file()`, `load_all_assessments()` |
| `notebooks/1.0.-step-1.ipynb` | Created | Verification notebook |

## Schema Issues Found and Handled

### Column headers
| Issue | Affected Files | Fix |
|---|---|---|
| `FIl` typo (capital I) in `G2 Fil Higher Emergent` | All three files | Rename `FIl` → `Fil` |
| `G2 Fil Transitioning` / `Developing` order swapped | 2024-25 vs 2025-26 | Reorder to canonical order |
| Extra Total columns (`G2 Total MT Assessed`, etc.) | 2025-26 only | Drop all grade-level Total columns |

### Data values — whitespace
| Issue | Affected Files | Fix |
|---|---|---|
| `'BARMM '` trailing whitespace in Region | 2024-25 BoSY + EoSY (29 rows each) | Strip all string columns |
| `'Lilo-an Integrated School '` trailing whitespace | 2025-26 BoSY (1 row) | Strip all string columns |

### Data values — mojibake (encoding corruption)
| Issue | Affected Files | Rows | Fix |
|---|---|---|---|
| `¤` (U+00A4) replacing `ñ` — e.g. `Due¤as` → `Dueñas`, `Osme¤a` → `Osmeña` | All three files (26 District + 2 School Name in 24-25; 2 School Name in 25-26) | ~28 per 24-25 file, 2 in 25-26 | Replace `¤` → `ñ` |
| `Ã±` double-encoded `ñ` — e.g. `DoÃ±a` → `Doña` | All three files (1 School Name each) | 1 per file | Replace `Ã±` → `ñ` |

Root cause: `¤` is `0xA4` in latin-1, which is the byte for `ñ` (`0xF1`) after a specific encoding round-trip corruption (`0xC2 0xA4` in UTF-8 = U+00A4). The 2025-26 file fixed the District column (`Dueñas`) but the School Name instances persist across all years.

### Data values — legitimate cross-year differences (not bugs)
| Column | Finding | Action |
|---|---|---|
| Division | 12 new divisions in 2025-26 (BARMM expansion: Basilan, Sulu, Tawi-Tawi, Lanao del Sur I/II, etc.) | No fix needed — real administrative changes |
| District | ~200 new districts in 2025-26 (same BARMM expansion); 3 renames with parentheticals dropped (e.g. `Aromar (Aromahan-Marulas)` → `Aromar`) | No fix needed — joins use School ID, not District name |
| Language | 1 new value in 2025-26: `Other` | No fix needed — new category |

## Canonical Column Schema (post-harmonization)

**17 non-grade columns** (unchanged across years):
`Region, Division, District, School ID, School Name, Language, Total Assessed, Low Emerging Reader, High Emerging Reader, Developing Reader, Transitioning Reader, Reading At Grade Level, Total Low Emerging, Total High Emerging, Total Developing, Total Transitioning, Total At Grade Level`

**30 grade-level columns** in canonical order (5 profiles × 6 grade-language groups):
```
G1: Lower Emergent, Higher Emergent, Developing, Transitioning, Grade Level
G2 MT: Lower Emergent, Higher Emergent, Developing, Transitioning, Grade Level
G2 Fil: Lower Emergent, Higher Emergent, Developing, Transitioning, Grade Level
G3 MT: Lower Emergent, Higher Emergent, Developing, Transitioning, Grade Level
G3 Fil: Lower Emergent, Higher Emergent, Developing, Transitioning, Grade Level
G3 Eng: Lower Emergent, Higher Emergent, Developing, Transitioning, Grade Level
```

**2 metadata columns** added by loader: `school_year`, `period`

Total: **49 columns** per loaded DataFrame.

## GCS Paths

**Raw** (input):
```
data_ecair_paaral/raw/CRLA Results Archive_SY 2024-25 Assessment Results_Table_BoSY.csv
data_ecair_paaral/raw/CRLA Results Archive_SY 2024-25 Assessment Results_Table_EoSY.csv
data_ecair_paaral/raw/CRLA National Dashboard_BoSY 2025-26 Assessment Results_Table.csv
```

**Modified** (output, for future steps): `data_ecair_paaral/modified/`

## Adding a New School Year

1. Upload CSV to `data_ecair_paaral/raw/`.
2. Add entry to `CRLA_RAW_FILES` dict in `preprocessing.py`.
3. Run `harmonize_columns()` — it will raise `ValueError` if new columns don't match the canonical set, signaling a schema change that needs handling.

## Audit Results (completed)
- [x] **Region**: Whitespace only (`BARMM `) — fixed by strip. Values identical after strip.
- [x] **Division**: No whitespace/encoding issues. 12 new divisions in 2025-26 (BARMM expansion) — legitimate.
- [x] **District**: `Due¤as` mojibake (fixed). ~200 new districts in 2025-26 (BARMM expansion). 3 parenthetical renames (e.g. `Aromar (Aromahan-Marulas)` → `Aromar`) — not patched since cross-year joins use School ID.
- [x] **School Name**: 2 mojibake instances (`Osme¤a ES`, `DoÃ±a E.J. Garcia ES`) — fixed. 1 trailing whitespace (`Lilo-an Integrated School `) — fixed by strip.
- [x] **Language**: 1 new value in 2025-26 (`Other`) — legitimate new category.
