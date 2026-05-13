# DepEd Assessment Analytics — Gold Layer

A reproducible pipeline that transforms raw DepEd school-level assessment exports into clean, school-indexed analytical parquets. Covers three instruments spanning Grades 1–10 across approximately 39,000 Philippine public schools.

---

## Instruments

### CRLA — Classroom Reading Level Assessment (Grades 1–3)

Early-grade reading. Administered at the beginning (BoSY) and end (EoSY) of each school year, with a mid-year checkpoint (MoSY) for intervention schools. Six grade-language groups: G1, G2 MT, G2 Fil, G3 MT, G3 Fil, G3 Eng.

| Ordinal | Level |
|---|---|
| 1 | Lower Emergent |
| 2 | Higher Emergent |
| 3 | Developing |
| 4 | Transitioning |
| 5 | Grade Level |

### PhilIRI — Philippine Informal Reading Inventory (Grades 4–10)

Reading comprehension administered in two stages. BoSY uses a group screening test (Grade Ready cutoff) followed by individualized graded passages for below-grade readers. EoSY re-assesses only students who were at Frustration or Instructional at BoSY. Split into KS2 (G4–G6) and KS3 (G7–G10), two languages each (Filipino, English).

Gold outputs use a 3-level collapsed scale for BoSY→EoSY comparison (Frustration / Instructional / Independent). Year-over-year BoSY comparisons use the full 7-level native scale.

### RMA — Rapid Mathematics Assessment (Grades 1–10)

Mathematics proficiency. No language split — one assessment per grade. Split into KS1 (G1–G3), KS2 (G4–G6), and KS3 (G7–G10).

| Ordinal | Level |
|---|---|
| 1 | Emerging Not Proficient |
| 2 | Emerging - Low Proficient |
| 3 | Developing - Nearly Proficient |
| 4 | Transitioning - Proficient |
| 5 | At Grade Level - Highly Proficient |

**Scales are not comparable across instruments.** CRLA and RMA share a 1–5 range but measure different constructs. PhilIRI uses a 1–3 scale.

---

## Data Availability

| Instrument | Timepoints available |
|---|---|
| CRLA | BoSY 2024-25, EoSY 2024-25, BoSY 2025-26, MoSY 2025-26, EoSY 2025-26 |
| PhilIRI KS2 | BoSY 2024-25, EoSY 2024-25, BoSY 2025-26, EoSY 2025-26 |
| PhilIRI KS3 | BoSY 2024-25, EoSY 2024-25, BoSY 2025-26, EoSY 2025-26 |
| RMA KS1 | EoSY 2024-25, BoSY 2025-26, EoSY 2025-26 |
| RMA KS2 | BoSY 2025-26, EoSY 2025-26 |
| RMA KS3 | BoSY 2025-26, EoSY 2025-26 |

RMA KS1 BoSY 2024-25 and all KS1 2023-24 files are excluded — see `data/gold/README.md` for details.

---

## What the Gold Layer Provides

Every school at every available timepoint gets a row in the timepoint file. Every school with data at both endpoints of a within-year period gets a row in the segments file. No rows are dropped; missing data propagates as NaN.

### Timepoint indicators

For each school × timepoint:

- **`ordinal_mean`** — weighted average of the proficiency distribution across grade(-language) groups. A value of 3.4 means the average learner at that school sits between the third and fourth level.
- **`ordinal_sd`** — spread of the distribution. High SD means learners are polarized across levels; low SD means they cluster together.
- **`ordinal_skew`** — asymmetry. Negative skew (national tendency) means most learners are at higher levels with a long lower tail.
- **`ordinal_kurt`**, **`bimodality_coef`** — higher-order shape descriptors. Bimodality coefficient > 0.555 flags distributions that are stretched toward both extremes simultaneously.
- **`groups_with_data`** — integer count of grade(-language) groups with complete data at this timepoint. Use as a data quality annotation.
- **`pct_gl`** (CRLA) / **`pct_grade_ready`** (PhilIRI BoSY) / **`pct_aglhp`** (RMA) — share of assessed learners at the top proficiency level.
- **`total_assessed`** — total students assessed at this school and timepoint.

### Segment indicators

For each school × within-year segment (BoSY → EoSY):

- **`delta_mean`** — change in ordinal mean from start to end of the segment. Positive = improvement.
- **`delta_sd`**, **`delta_skew`** — changes in spread and asymmetry.
- **`emd_mean`** — mean Earth Mover's Distance (Wasserstein-1) across grade groups. Measures how much the distribution shifted, regardless of direction. A school where many learners moved up one level has the same delta_mean as one where fewer moved up two levels, but different EMD.

### Year-over-year indicators (PhilIRI only)

For each school appearing in both BoSY 2024-25 and BoSY 2025-26:

- **`delta_mean`** on the 7-level native BoSY scale — compares cohorts at the same point in the school year across years.
- **`delta_pct_grade_ready`**, **`delta_pct_3ld`** — changes in the share of Grade Ready students and deep-need (3 levels down) students.
- **`count_stable`** — informational flag for schools where assessed counts changed by more than 25% between cohorts.

Full column schemas: [`data/gold/README.md`](data/gold/README.md)

---

## National Snapshot (CRLA)

| Timepoint | Ordinal Mean | SD | Skewness |
|---|---|---|---|
| BoSY 2024-25 | 3.30 | 1.07 | −0.49 |
| EoSY 2024-25 | 4.13 | 0.87 | −1.18 |
| BoSY 2025-26 | 3.06 | 1.08 | −0.31 |
| MoSY 2025-26 | 3.23 | 0.96 | −0.41 |
| EoSY 2025-26 | 4.15 | 0.83 | −1.13 |

Within-year gains: **+0.82** ordinal levels (SY 2024-25), **+1.10** (SY 2025-26). The national EoSY mean consistently exceeds ordinal 4 (Transitioning level) by end of year.

---

## Repository Structure

```
project_crla/
│
├── data/
│   ├── bronze/                    Raw CSV exports per instrument
│   │   ├── crla/
│   │   ├── philiri/
│   │   └── rma/
│   ├── silver/                    Harmonized, typed parquets (one per timepoint)
│   │   ├── crla/
│   │   ├── philiri/
│   │   └── rma/
│   └── gold/                      School-level analytical indicators
│       └── README.md              Full file inventory and column schemas
│
├── modules/                       Pipeline library
│   ├── preprocessing.py           CRLA schema harmonization and loading
│   ├── philiri_preprocessing.py   PhilIRI file discovery and preprocessing
│   ├── rma_preprocessing.py       RMA file discovery and preprocessing
│   ├── analysis.py                Ordinal moments, EMD, chain progress (CRLA)
│   ├── priority_ranking.py        School priority ranking (CRLA)
│   ├── sensitivity_analysis.py    Ranking robustness analysis (CRLA)
│   ├── lgu_matching.py            School-to-LGU revenue crosswalk (CRLA)
│   └── output.py                  Output utilities
│
├── scripts/                       Executable pipeline entry points
│   ├── build_silver.py            Bronze → silver for all instruments
│   ├── build_gold.py              Silver → gold for CRLA
│   ├── build_gold_philiri.py      Silver → gold for PhilIRI
│   ├── build_gold_rma.py          Silver → gold for RMA
│   └── build_composite_ranking.py CRLA priority ranking output
│
├── notebooks/                     Exploratory and stakeholder notebooks
├── documentation/                 Methodology references per pipeline stage
└── dashboard/                     Streamlit dashboard
```

---

## Rebuilding the Data

```bash
# Bronze → silver (harmonize and type all raw exports)
python scripts/build_silver.py [--crla] [--philiri] [--rma]

# Silver → gold (compute school-level indicators)
python scripts/build_gold.py
python scripts/build_gold_philiri.py
python scripts/build_gold_rma.py
```

With no flags, `build_silver.py` processes all three instruments. Each gold script is independent and can be run selectively.

---

## Design Principles

**No validity gates.** Every school present in the silver layer has a row in the gold layer. NaN in any computed column means the underlying data was absent or had a zero denominator — it is not an exclusion. Downstream users apply their own filters using `groups_with_data` and `total_assessed`.

**Ordinal scoring over PCA.** Fixed ordinal weights (1 through the number of levels) are used rather than PCA-derived weights. PCA weights proved unstable across reference timepoints — the ordinal method uses weights that are fixed, interpretable, and require no reference period.

**Within-year segments only.** Segment deltas are computed only within a single school year (BoSY → EoSY). Cross-year deltas conflate school performance with cohort turnover and are not produced.

---

## AI Disclosure

AI coding assistants (Claude, Anthropic) were used during development for code review, documentation drafting, and structured prompt generation. All methodological decisions, domain interpretations, and final outputs were made and validated by the ECAIR team.
