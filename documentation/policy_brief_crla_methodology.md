# A Data-Driven Framework for Targeting Literacy Interventions Using DepEd's Existing CRLA Data

**Education Center for AI Research (ECAIR), Department of Education**

---

## Background

DepEd's Classroom Reading Level Assessment (CRLA) assesses over 10 million Grades 1–3 learners across ~39,000 public elementary schools every BoSY and EoSY, producing 30 structured data points per school per cycle. This data is already collected on a fixed national schedule at the frequency needed for longitudinal tracking. Two additional government datasets — the DepEd School Level Database with PSGC codes (linking schools to municipalities) and the DOF-BLGF Statement of Receipts and Expenditures (providing LGU fiscal data including the Special Education Fund) — can be joined to the CRLA without new data collection. Together, these three routinely produced datasets enable a school-level priority framework combining academic need, student population, and local fiscal capacity.

## Proposed Method

The pipeline transforms raw CRLA data into a transparent, reproducible priority ranking through four components:

**1. Three measures per school, not just an average.** Each school's proficiency distribution is captured by its mean (average level, 1–5 scale), standard deviation (within-school inequality), and skewness (whether strugglers or advanced readers dominate). Two schools can share the same mean yet need different interventions — one with students clustered at Developing, another split between Lower Emergent and Grade Level. Tracking all three measures over time reveals whether gains are broad-based or leave students behind.

**2. Data quality gates.** Schools must report all three grade levels, at least four of six grade-language groups, and at least 15 assessed learners per reporting group to enter the ranking. This excludes ~35% of schools — not as unimportant, but as insufficiently measured for reliable ranking.

**3. Three-pillar priority ranking.** The composite score is the product of percentile ranks across Need (proficiency level, trajectory, inequality, and distribution shape), Impact (assessed learner count), and Capacity Gap (inverse of LGU Special Education Fund per enrolled learner). A school must rank high on all three dimensions to reach the top — no single factor dominates.

**4. Robustness verification.** Testing 500 random weight configurations confirms that 60% of schools show near-zero rank volatility and the top-100 targets are stable regardless of weight specification.

## Sustainability

The pipeline runs on DepEd's existing CRLA collection cycle. When new assessment data arrives, a single file is added and the system automatically produces updated scores, validation results, and rankings — no methodological changes, new instruments, or additional burden on schools. Each new cycle extends the longitudinal chain without invalidating prior results.

## What This Enables

- **Division and regional offices**: a defensible basis for allocating reading intervention resources that accounts for need, student reach, and local fiscal capacity simultaneously.
- **Central office**: a national view of where literacy gains and summer learning loss are concentrated, and which priority schools are robust to methodological choices.
- **Monitoring and evaluation**: a built-in before-and-after framework — schools receiving interventions are tracked across subsequent CRLA cycles with the same pipeline and validation standards.

---

*ECAIR, Department of Education. Full pipeline, documentation, and reproducibility materials available for review.*
