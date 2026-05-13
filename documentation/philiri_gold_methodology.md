# PhilIRI Gold Layer — Methodology

This document records the design decisions behind the PhilIRI gold layer: how raw assessment counts are transformed into analytical indicators, what assumptions are made, and why. All decisions are tied to the source instrument documentation.

**Source instrument**: *Philippine Informal Reading Inventory (Phil-IRI) Manual 2018*, Department of Education, Bureau of Learning Resources. File: `documentation/Phil-IRI Full Package v1.pdf`.

---

## 1. Instrument Overview

PhilIRI is administered in two stages, at the Beginning of School Year (BoSY) and End of School Year (EoSY). The two stages are structurally different.

### Stage 1 — BoSY: Group Screening Test (GST)

All enrolled students in Grades 4–10 take a 20-item silent reading comprehension test. The outcome is one of three classifications (Manual, pp. 8–9):

| GST score | Classification | Individual follow-up |
|---|---|---|
| ≥ 14 / 20 | **Grade Ready** | None — student is reading at or near grade level |
| 8–13 / 20 | Below grade; start individual test **2 levels below grade** | Yes |
| 0–7 / 20 | Below grade; start individual test **3 levels below grade** | Yes |

Students who scored below 14 then undergo the **Phil-IRI Graded Passages** — an individualized oral reading assessment. Starting from 2 or 3 grade levels below the student's current grade, the examiner moves up and down through levelled passages until three reading levels are determined (Manual, pp. 10–12):

- **Independent**: student reads without assistance (97–100% word accuracy, 80–100% comprehension)
- **Instructional**: reads with teacher support (90–96% accuracy, 59–79% comprehension)
- **Frustration**: cannot read even with support (≤ 89% accuracy, ≤ 58% comprehension)

The school-level dashboard data aggregates these outcomes into seven BoSY categories per grade-language group:

| Column label | Meaning |
|---|---|
| `Grade Ready` | Passed GST (score ≥ 14); reading at/near grade level |
| `2LD Independent` | Final reading level: independent, ~2 grades below current grade |
| `2LD Instructional` | Final reading level: instructional, ~2 grades below current grade |
| `2LD Frustration` | Frustrated at ~2 grades below current grade (rare; see §1.1) |
| `3LD Independent` | Final reading level: independent, ~3 grades below current grade |
| `3LD Instructional` | Final reading level: instructional, ~3 grades below current grade |
| `3LD Frustration` | Frustrated even at ~3 grades below current grade (lowest) |

The ordinal ordering from worst to best reading level is therefore:

```
3LD Frustration < 3LD Instructional < 3LD Independent
  < 2LD Frustration < 2LD Instructional < 2LD Independent
  < Grade Ready
```

The **levels-down axis** (3LD vs 2LD) is primary; the **performance axis** (Frustration / Instructional / Independent) is secondary within each LD group. A student at 3LD-Independent is reading at a lower absolute level than one at 2LD-Frustration, because their starting test was placed one grade level lower by design (Manual, p. 16, Table 3).

#### 1.1 Why 2LD Frustration counts are near zero

The manual's protocol (pp. 10–11, Figure 2) requires the examiner to continue giving lower-level passages when a student shows Frustration at the starting level. A student who starts at the 2LD level and shows Frustration would then be tested at the 3LD level. Consequently, students who are ultimately frustrated even at 2LD should appear in the 3LD category, not under 2LD Frustration. Non-zero 2LD Frustration counts in the data indicate incomplete individual assessment administration at that school.

### Stage 2 — EoSY: Graded Passages (Post-Test)

Only students who were at Frustration or Instructional at BoSY are re-assessed at EoSY (Manual, pp. 12, Stage 4). Students who were Grade Ready at BoSY are not individually re-tested — they are carried forward and implicitly counted as Independent at EoSY.

EoSY reports three categories per grade-language group:

| EoSY label | Meaning |
|---|---|
| `Independent` | Now reading independently at their assessed level (includes BoSY Grade Ready pass-throughs) |
| `Instructional` | Still requires teacher support |
| `Frustration` | Still frustrated at their assessed level |

**Critical structural implication**: EoSY Assessed ≤ BoSY (Frustrated + Instructional). Schools where EoSY Assessed exceeds this bound by more than 10% are flagged as having inconsistent data (see §4.1).

---

## 2. Three-Level Collapse for BoSY→EoSY Comparison

EoSY reports only three levels. To enable direct comparison between BoSY and EoSY distributions — and to compute delta_mean and EMD across timepoints — BoSY must be mapped to the same three-level scale.

### 2.1 Mapping

| Ordinal | Collapsed label | BoSY categories included | EoSY category |
|---|---|---|---|
| 3 | **Independent** | `2LD Independent`, `Grade Ready` | `Independent` |
| 2 | **Instructional** | `2LD Instructional`, `3LD Independent` | `Instructional` |
| 1 | **Frustration** | `2LD Frustration` (rare), `3LD Instructional`, `3LD Frustration` | `Frustration` |

### 2.2 Rationale for the placement of 3LD Independent

The most deliberate judgment call is assigning `3LD Independent` to ordinal level 2 (Instructional) rather than level 3 (Independent). The reasoning:

A student classified as 3LD Independent can read without support — but only at a text that is 3 grade levels below their current grade. Their absolute reading level is lower than that of a student who is at 2LD Instructional (who was placed 2 levels below grade for the individualized test). For school prioritization purposes, treating a 3LD-Independent student as equivalent to an Independent reader would understate the school's need. The placement in ordinal level 2 acknowledges the demonstrated performance at the tested level while preserving the signal that the school still has students reading far below grade.

This assumption must be carried into any downstream interpretation: **the PhilIRI 3-level ordinal scale measures relative improvement within a student's tested level, not absolute grade-level proficiency**.

### 2.3 Denominator for BoSY percentages

The `{G} Assessed` column in KS2 BoSY represents the combined total for both Fil and Eng. It is **not** suitable as a per-language denominator. The per-language denominator is derived from the column sum:

```
G4 Fil denominator = G4 Fil Grade Ready
                   + G4 2LD Fil Frustration + G4 2LD Fil Instructional + G4 2LD Fil Independent
                   + G4 3LD Fil Frustration + G4 3LD Fil Instructional + G4 3LD Fil Independent
```

KS3 BoSY provides `{G} Fil Assessed` and `{G} Eng Assessed` explicitly, but we use the derived column sum uniformly across all BoSY files for consistency.

### 2.4 Denominator for EoSY percentages

EoSY has no `Grade Ready` category. The denominator is the sum of the three EoSY levels:

```
G4 Fil denominator = G4 Fil Frustration + G4 Fil Instructional + G4 Fil Independent
```

This applies to both KS2 and KS3 EoSY across all school years.

**KS3 EoSY 2024-25 special case**: This file provides one combined `{G} Assessed` column per grade rather than per-language Assessed columns. We do **not** use that column as the denominator. Instead, we use the derived per-language column sum (same formula as above), which is both more accurate and consistent with the 2025-26 EoSY format.

---

## 3. Gold File Schema

Three gold files are produced per key stage (KS2 and KS3 separately).

### 3.1 `philiri_{ks}_school_timepoints.parquet`

One row per (School ID × timepoint). Timepoints: BoSY 2024-25, EoSY 2024-25, BoSY 2025-26, EoSY 2025-26.

| Column | Description |
|---|---|
| `school_year`, `period`, `ks` | Timepoint tags |
| `ordinal_mean` | Mean of 3-level ordinal (1–3) across all grade-language groups |
| `ordinal_sd` | SD of ordinal distribution across groups |
| `ordinal_skew` | Skewness of ordinal distribution |
| `ordinal_kurt` | Excess kurtosis |
| `bimodality_coef` | BC = (skew² + 1) / regular kurtosis |
| `pct_grade_ready` | **BoSY only**: proportion of assessed students classified as Grade Ready |
| `pct_3ld` | **BoSY only**: proportion classified as any 3LD category (depth-of-need indicator) |
| `total_assessed` | Total students assessed at this timepoint |
| `valid` | At least one grade-language group has data |
| `valid_strict` | All grades present + ≥ 4 groups + ≥ 15 assessed per group |

### 3.2 `philiri_{ks}_school_segments.parquet`

One row per (School ID × segment). Segments: Learning 2024-25 (BoSY→EoSY), Learning 2025-26 (BoSY→EoSY). Uses the **3-level collapsed scale** at both endpoints.

| Column | Description |
|---|---|
| `segment_label` | e.g. `Learning_2024-25` |
| `delta_mean` | EoSY ordinal_mean − BoSY ordinal_mean (3-level scale) |
| `delta_sd`, `delta_skew` | Changes in SD and skewness |
| `emd_mean` | Earth Mover's Distance between BoSY and EoSY distributions |
| `valid` | Both endpoints valid AND plausibility check passed |
| `valid_strict` | Both endpoints valid_strict AND plausibility check passed |
| `eosy_plausible` | EoSY Assessed ≤ 1.10 × BoSY (F + I) students (see §4.1) |

### 3.3 `philiri_{ks}_bosy_yoy.parquet`

One row per School ID. Compares BoSY 2024-25 to BoSY 2025-26 using the **full 7-level BoSY scale** (3LD-F=1 through Grade Ready=7).

Using the richer 7-level scale here is appropriate because both endpoints share the same BoSY schema; the 3-level collapse is not needed. The 7-level scale preserves depth-of-need information that the collapse discards.

Ordinal weights: 3LD-F=1, 3LD-I=2, 3LD-Ind=3, 2LD-F=4, 2LD-I=5, 2LD-Ind=6, Grade Ready=7.

| Column | Description |
|---|---|
| `delta_mean` | BoSY 2025-26 ordinal_mean − BoSY 2024-25 ordinal_mean (7-level scale) |
| `delta_sd`, `delta_skew` | Changes in SD and skewness |
| `delta_pct_grade_ready` | Change in Grade Ready fraction (BoSY 2025-26 − BoSY 2024-25) |
| `delta_pct_3ld` | Change in deep-need fraction |
| `emd_mean` | EMD between BoSY 2024-25 and BoSY 2025-26 distributions (7-level scale) |
| `valid` | Both endpoints valid AND count_stable |
| `valid_strict` | Both endpoints valid_strict AND count_stable |
| `count_stable` | \|assessed_2526 − assessed_2425\| / assessed_2425 ≤ 0.25 |

---

## 4. Validity Checks

### 4.1 BoSY→EoSY Plausibility Check (`eosy_plausible`)

Unlike CRLA — where both BoSY and EoSY assess all students — PhilIRI EoSY only re-assesses students who were at Frustration or Instructional at BoSY. EoSY Assessed is therefore expected to be lower than BoSY Assessed. Applying the CRLA count-stability check (|EoSY − BoSY| / BoSY ≤ 0.25) would be incorrect here.

The appropriate check is:

```
EoSY Assessed ≤ 1.10 × BoSY non-Grade-Ready students
```

"Non-Grade-Ready" is defined as all students who underwent the Graded Passages individual test at BoSY (i.e., all 2LD and 3LD students: Frustration, Instructional, and Independent at those levels). This is the maximum theoretical pool eligible for EoSY re-assessment. It is used instead of the narrower "F+I only" ceiling because in practice it is a more robust bound: students recorded as Independent at BoSY may have been placed in re-assessment at some schools, and the wider ceiling avoids false positives from minor data inconsistencies.

A school where EoSY Assessed exceeds 110% of the BoSY non-Grade-Ready count has more students re-assessed than ever took the individual BoSY test — which is inconsistent with the assessment design and likely indicates a data entry error.

### 4.2 Year-over-Year Count Stability (`count_stable`)

For YoY BoSY comparisons, both timepoints are full assessments. The standard 25% threshold applies:

```
|BoSY_2526_assessed − BoSY_2425_assessed| / BoSY_2425_assessed ≤ 0.25
```

Schools exceeding this threshold are excluded from the YoY BoSY file's `valid` flag.

### 4.3 `valid_strict` Criteria

Mirrors the CRLA definition: all expected grade levels present + ≥ 4 grade-language groups with data + minimum 15 assessed per group.

---

## 5. Relationship to CRLA

PhilIRI (G4–G10) and CRLA (G1–G3) are complementary instruments with no grade overlap. They are not directly comparable in scoring methodology:

- CRLA uses a fixed 5-level ordinal scale (LE=1 through GL=5) at both BoSY and EoSY, enabling direct delta_mean comparison.
- PhilIRI uses a 7-level BoSY scale and a 3-level EoSY scale; cross-timepoint comparison requires the collapse described in §2.

The PhilIRI 3-level ordinal_mean is not comparable in magnitude to the CRLA 5-level ordinal_mean.
