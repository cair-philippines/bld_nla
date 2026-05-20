# Assessment Platform — Data Handoff

This document is the data contract between the assessment analytics pipeline
(`project_crla`) and the assessment platform frontend. It covers what data is
available, where it lives, how to derive the specific metrics the platform
needs, and what external data sources the platform depends on.

---

## Platform Overview

Two views:

| View | Purpose |
|---|---|
| **Dashboard** | Schools ranked by assessment signals; raw lower-band student counts |
| **Map** | Public school nodes with assessment performance; teacher education institution nodes for proximity analysis against underperforming schools |

**Tech stack:** Next.js / React. Gold and silver parquets are served from a backend
(Python/FastAPI or similar); they are not committed to the repository and must not
be bundled as static assets.

---

## Source Project

**Location:** `/workspace/innovation-projects/project_crla`  
**GitHub:** `git@github.com:cair-philippines/bld_nla.git`

---

## Instruments and Scales

Three instruments spanning Grades 1–10. **Scales are not comparable across
instruments** — CRLA and RMA share a 1–5 range but measure different constructs
(reading vs. mathematics). PhilIRI uses a separate 1–3 scale.

### CRLA — Classroom Reading Level Assessment (Grades 1–3)

5-level ordinal scale. Six grade-language groups: G1, G2 MT, G2 Fil, G3 MT,
G3 Fil, G3 Eng.

| Ordinal | Level | Short |
|---|---|---|
| 1 | Lower Emergent | LE |
| 2 | Higher Emergent | HE |
| 3 | Developing | Dev |
| 4 | Transitioning | Trans |
| 5 | Grade Level | GL |

### PhilIRI — Philippine Informal Reading Inventory (Grades 4–10)

Two key stages: KS2 (G4–G6), KS3 (G7–G10). Two languages per grade (Filipino,
English).

Gold and EoSY silver use a **3-level collapsed scale**. BoSY silver uses the raw
7-level native scale (collapse must be applied at query time — see
[Lower-Band Computation: PhilIRI BoSY](#philiri-bosy) below).

**3-level collapsed scale (gold and EoSY silver):**

| Ordinal | Level |
|---|---|
| 1 | Frustration |
| 2 | Instructional |
| 3 | Independent |

**7-level native BoSY scale (BoSY silver only):**

| Ordinal | Level |
|---|---|
| 1 | 3LD Frustration |
| 2 | 3LD Instructional |
| 3 | 3LD Independent |
| 4 | 2LD Frustration |
| 5 | 2LD Instructional |
| 6 | 2LD Independent |
| 7 | Grade Ready |

**Collapse mapping (BoSY 7-level → 3-level):**

| Collapsed level | Native BoSY sources |
|---|---|
| Frustration | 2LD Frustration, 3LD Instructional, 3LD Frustration |
| Instructional | 2LD Instructional, 3LD Independent |
| Independent | 2LD Independent, Grade Ready |

Note: 3LD Independent maps to Instructional (not Independent).

### RMA — Rapid Mathematics Assessment (Grades 1–10)

Three key stages: KS1 (G1–G3), KS2 (G4–G6), KS3 (G7–G10). No language split.

| Ordinal | Level | Short |
|---|---|---|
| 1 | Emerging Not Proficient | ENP |
| 2 | Emerging - Low Proficient | ELP |
| 3 | Developing - Nearly Proficient | DNP |
| 4 | Transitioning - Proficient | TP |
| 5 | At Grade Level - Highly Proficient | AGLHP |

---

## Data Availability

| Instrument | Timepoints |
|---|---|
| CRLA | BoSY 2024-25, EoSY 2024-25, BoSY 2025-26, MoSY 2025-26, EoSY 2025-26 |
| PhilIRI KS2 | BoSY 2024-25, EoSY 2024-25, BoSY 2025-26, EoSY 2025-26 |
| PhilIRI KS3 | BoSY 2024-25, EoSY 2024-25, BoSY 2025-26, EoSY 2025-26 |
| RMA KS1 | EoSY 2024-25, BoSY 2025-26, EoSY 2025-26 |
| RMA KS2 | BoSY 2025-26, EoSY 2025-26 |
| RMA KS3 | BoSY 2025-26, EoSY 2025-26 |

RMA KS1 BoSY 2024-25 is excluded (School IDs not populated in the source export).
No RMA year-over-year files exist.

---

## Data Layer Strategy

The platform needs **two layers** for different purposes:

| Layer | Use | Location |
|---|---|---|
| **Gold** | School rankings, ordinal means, deltas, top-level shares | `data/gold/` |
| **Silver** | Exact per-level raw student counts (lower-band computation) | `data/silver/` |

Both are gitignored and must be regenerated from bronze CSVs (see
[Rebuild Commands](#rebuild-commands)) or fetched from a shared storage location.

---

## Gold Layer — Rankings and Summary Indicators

### Join key

`School ID` (int64) is the shared primary key across all gold files. Links to
school coordinates via the crosswalk in `project_coordinates`
(see [School Coordinates](#school-coordinates)).

### File inventory

| File | Rows | Schools | Notes |
|---|---|---|---|
| `crla_school_timepoints.parquet` | 188,348 | 39,447 | 5 timepoints |
| `crla_school_segments.parquet` | 259,148 | 39,335 | 7 segments |
| `philiri_ks2_school_timepoints.parquet` | 147,687 | 38,966 | 4 timepoints |
| `philiri_ks2_school_segments.parquet` | 73,319 | 38,726 | 2 segments |
| `philiri_ks3_school_timepoints.parquet` | 41,446 | 11,004 | 4 timepoints |
| `philiri_ks3_school_segments.parquet` | 20,496 | 10,923 | 2 segments |
| `rma_ks1_school_timepoints.parquet` | 114,925 | 39,303 | 3 timepoints |
| `rma_ks1_school_segments.parquet` | 38,912 | 38,912 | 1 segment |
| `rma_ks2_school_timepoints.parquet` | 76,619 | 38,567 | 2 timepoints |
| `rma_ks2_school_segments.parquet` | 38,332 | 38,332 | 1 segment |
| `rma_ks3_school_timepoints.parquet` | 21,734 | 10,972 | 2 timepoints |
| `rma_ks3_school_segments.parquet` | 10,882 | 10,882 | 1 segment |

PhilIRI YoY files (`philiri_{ks}_bosy_yoy.parquet`) exist but are not needed for
platform v1.

Full column schemas: `data/gold/README.md`.

### Columns relevant to the platform

**Timepoint files (primary source for dashboard ranking and map nodes):**

| Column | Type | Description |
|---|---|---|
| `School ID` | int64 | Join key |
| `school_year` | str | `2024-25` or `2025-26` |
| `period` | str | `BoSY`, `MoSY`, or `EoSY` |
| `timepoint_label` | str | e.g. `BoSY 2024-25` |
| `ordinal_mean` | float | Weighted avg proficiency across grade groups — primary ranking signal |
| `total_assessed` | int | Total students assessed at this school × timepoint |
| `pct_gl` | float | CRLA: % at Grade Level |
| `pct_grade_ready` | float | PhilIRI BoSY only: % at Grade Ready |
| `pct_aglhp` | float | RMA: % at At Grade Level - Highly Proficient |
| `groups_with_data` | int | Grade groups with complete data; use as data quality annotation |
| `School Name` | str | Display name |
| `Region`, `Division`, `District` | str | Administrative hierarchy |

**Segment files (for within-year learning gain signals):**

| Column | Type | Description |
|---|---|---|
| `School ID` | int64 | Join key |
| `segment_label` | str | e.g. `Learning_2024-25` |
| `delta_mean` | float | `ordinal_mean(EoSY) − ordinal_mean(BoSY)` — positive = improvement |
| `delta_sd` | float | Change in spread |
| `emd_mean` | float | Earth Mover's Distance — distributional shift regardless of direction |

### NaN semantics

NaN in any computed column means the underlying data was absent or had a zero
denominator. No rows are dropped — every school in the silver layer has a row in
gold. NaN is not an exclusion; it is a missing-data marker. The platform should
surface NaN schools (e.g., "No data available") rather than silently omitting them.

---

## Silver Layer — Exact Per-Level Raw Student Counts

The gold layer does not store per-level raw counts. Load silver for exact
lower-band student counts.

### File locations and naming

```
data/silver/crla/       {sy}_{period}.parquet
data/silver/philiri/    {ks}_{sy}_{period}.parquet
data/silver/rma/        {ks}_{sy}_{period}.parquet
```

**Examples:**
```
data/silver/crla/2024-25_BoSY.parquet
data/silver/philiri/ks2_2024-25_BoSY.parquet
data/silver/philiri/ks3_2025-26_EoSY.parquet
data/silver/rma/ks1_2025-26_BoSY.parquet
```

All silver files are indexed by `School ID` (int64).

### Column structure by instrument

**CRLA silver** — one row per school, columns:
```
School Name, Region, Division, District, Language,
Total Assessed, total_assessed, school_year, period,

# Per-grade-language group raw counts (6 groups × 5 levels = 30 columns):
G1 Lower Emergent, G1 Higher Emergent, G1 Developing, G1 Transitioning, G1 Grade Level,
G2 MT Lower Emergent, ..., G2 MT Grade Level,
G2 Fil Lower Emergent, ..., G2 Fil Grade Level,
G3 MT Lower Emergent, ..., G3 MT Grade Level,
G3 Fil Lower Emergent, ..., G3 Fil Grade Level,
G3 Eng Lower Emergent, ..., G3 Eng Grade Level,

# Convenience school-level aggregates (sum across all groups):
Total Low Emerging, Total High Emerging, Total Developing,
Total Transitioning, Total At Grade Level
```

**PhilIRI EoSY silver** — one row per school, columns:
```
School Name, Region, Division, District, school_year, period, ks,

# Per-grade per-language raw counts on 3-level collapsed scale:
G4 Assessed, G4 Fil Frustration, G4 Fil Instructional, G4 Fil Independent,
             G4 Eng Frustration, G4 Eng Instructional, G4 Eng Independent,
G5 Assessed, G5 Fil Frustration, ...
G6 Assessed, G6 Fil Frustration, ...   (KS2)
G7–G10 equivalents for KS3
```

**PhilIRI BoSY silver** — one row per school, columns:
```
School Name, Region, Division, District, school_year, period, ks,

# Per-grade per-language raw counts on 7-level native scale:
G4 Assessed,
G4 Fil Grade Ready, G4 2LD Fil Frustration, G4 2LD Fil Instructional,
G4 2LD Fil Independent, G4 3LD Fil Frustration, G4 3LD Fil Instructional,
G4 3LD Fil Independent,
G4 Eng Grade Ready, G4 2LD Eng Frustration, ...
G5 Assessed, ...
G6 Assessed, ...   (KS2; G7–G10 for KS3)
```

Note: PhilIRI silver has no `total_assessed` column. Use `sum({grade} Assessed for
all grades in KS)` to derive total students assessed at a school.

**RMA silver** — one row per school, columns:
```
School Name, Region, Division, District, total_assessed, school_year, period, ks,

# Per-grade raw counts (KS1 shown; KS2 = G4–G6, KS3 = G7–G10):
G1 Assessed, G1 Emerging Not Proficient, G1 Emerging - Low Proficient,
             G1 Developing - Nearly Proficient, G1 Transitioning - Proficient,
             G1 At Grade Level - Highly Proficient,
G2 Assessed, G2 Emerging Not Proficient, ...
G3 Assessed, G3 Emerging Not Proficient, ...
```

---

## Lower-Band Definitions and Computation

### CRLA — levels 1–2 (Lower Emergent + Higher Emergent)

**Recommended:** use the precomputed aggregate columns directly.

```python
crla_lower_band = df["Total Low Emerging"] + df["Total High Emerging"]
```

If you need to verify or recompute from grade-group columns:

```python
groups = ["G1", "G2 MT", "G2 Fil", "G3 MT", "G3 Fil", "G3 Eng"]
cols = [f"{g} Lower Emergent" for g in groups] + [f"{g} Higher Emergent" for g in groups]
crla_lower_band = df[cols].sum(axis=1)
```

### PhilIRI — level 1 (Frustration)

**EoSY silver** — Frustration column exists directly:

```python
# KS2 example (G4–G6, Fil and Eng)
frustration_cols = [
    "G4 Fil Frustration", "G4 Eng Frustration",
    "G5 Fil Frustration", "G5 Eng Frustration",
    "G6 Fil Frustration", "G6 Eng Frustration",
]
philiri_lower_band = df[frustration_cols].sum(axis=1)
```

<a name="philiri-bosy"></a>
**BoSY silver** — apply the collapse to extract Frustration counts:

```python
# Frustration = 2LD Frustration + 3LD Instructional + 3LD Frustration
# KS2 example (G4–G6, Fil and Eng)
grades = ["G4", "G5", "G6"]
langs = ["Fil", "Eng"]
frustration_cols = []
for g in grades:
    for lang in langs:
        frustration_cols += [
            f"{g} 2LD {lang} Frustration",
            f"{g} 3LD {lang} Instructional",
            f"{g} 3LD {lang} Frustration",
        ]
philiri_lower_band = df[frustration_cols].sum(axis=1)
```

KS3 uses grades G7–G10 with the same column pattern.

### RMA — levels 1–2 (Emerging Not Proficient + Emerging - Low Proficient)

```python
# KS1 example (G1–G3)
grades = ["G1", "G2", "G3"]
cols = (
    [f"{g} Emerging Not Proficient" for g in grades] +
    [f"{g} Emerging - Low Proficient" for g in grades]
)
rma_lower_band = df[cols].sum(axis=1)
```

KS2 uses G4–G6; KS3 uses G7–G10.

---

## School Coordinates

School lat/lon and the canonical school ID crosswalk are in a separate project:

**Project:** `project_coordinates`  
**Crosswalk file:** `data/gold/public_school_id_crosswalk.parquet`

This parquet maps `School ID` (int64) to school name, administrative hierarchy
(Region, Division, District), and geographic coordinates. Join all assessment data
to this file on `School ID` to get map node positions.

---

## Teacher Education Institutions

Data source TBD — to be resolved in the platform thread. The map view should
anticipate a second node type (`type: "HEI"`) with at minimum:

- Institution name
- Lat/lon
- One or more teacher education program flags (e.g., `has_bsed`, `has_baed`)

The proximity analysis between HEI nodes and underperforming school nodes will
require the same distance infrastructure used elsewhere in the ECAIR platform
stack (`project_ugnay` dense distance matrix or a spatial query at runtime).

---

## Rebuild Commands

If parquets need to be regenerated from raw bronze CSVs (run from project root):

```bash
# Bronze → silver
python scripts/build_silver.py --crla --philiri --rma

# Silver → gold
python scripts/build_gold.py
python scripts/build_gold_philiri.py
python scripts/build_gold_rma.py
```

Full pipeline documentation: `data/gold/README.md`.

---

## Key Invariants the Platform Must Respect

1. **Scales are not comparable across instruments.** Never display CRLA and RMA
   ordinal means on the same axis or combine them into a single score.

2. **NaN is not zero.** A school with NaN `ordinal_mean` had no data, not a score
   of zero. Display it distinctly.

3. **`groups_with_data` is informational, not a gate.** The gold layer computes
   metrics for every school regardless of how many grade groups had data. Use
   `groups_with_data` as a display annotation (e.g., a data quality badge), never
   as a filter that drops rows.

4. **Within-year segments only.** `delta_mean` is always BoSY→EoSY within a
   single school year. Cross-year comparisons are not in the data and should not
   be implied.

5. **PhilIRI EoSY assesses a subset, not all students.** EoSY re-assesses only
   students who were at Frustration or Instructional at BoSY. `total_assessed`
   at EoSY will therefore be smaller than at BoSY for the same school and year.
   Do not present EoSY counts as whole-school enrollment figures.
