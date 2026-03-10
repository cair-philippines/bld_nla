# A Data-Driven Framework for Targeting Literacy Interventions Using DepEd's Existing CRLA Data

**Center for Artificial Intelligence Research (CAIR), De La Salle University**
**In partnership with the Department of Education**

---

## The Problem

DepEd administers the Classroom Reading Level Assessment (CRLA) to over 10 million learners in Grades 1–3 across roughly 39,000 public elementary schools every beginning and end of school year. This produces a rich dataset — student counts across five proficiency levels for six grade-language groups per school — but it has historically been underutilized for systematic intervention planning. Earlier analyses relied on a single composite score per school, applied minimal data quality filters, and did not account for school size or local government fiscal capacity when identifying where interventions are most needed.

The result: priority lists that included schools with unreliable data, ignored distributional inequality within schools, and treated a 50-student school the same as a 2,000-student school.

## What We Propose

We propose a reproducible analytical pipeline that transforms raw CRLA data — already collected by DepEd — into a principled, transparent priority ranking of schools for literacy intervention. The pipeline requires no new data collection. It works with the CSVs that DepEd already generates, supplemented by two publicly available administrative datasets: the DepEd School Level Database with Philippine Standard Geographic Codes (PSGC) and the Department of Finance's Statement of Receipts and Expenditures by LGU.

The method has four components:

**1. Three statistical moments, not just an average.** Each school's proficiency distribution is summarized by its mean (where is the average learner?), standard deviation (how unequal are learners within the school?), and skewness (are most learners above or below the average?). Two schools can share the same mean of 3.0 — one with students uniformly at the Developing level, another split between Lower Emergent and Grade Level. These schools need different interventions, and the three moments distinguish them. National results from SY 2024-25 show that while the mean rose from 3.30 to 4.13 during the school year, the SD dropped from 1.07 to 0.87 — indicating that instruction successfully narrowed the gap between stronger and weaker readers. Over the summer break, both gains reversed.

**2. Data quality gates that protect the ranking.** Not every school has enough data for a reliable score. We apply strict validation: a school must report data for all three grade levels, at least four of six grade-language groups, and at least 15 assessed learners per reporting group. This filters out roughly 35% of schools — not because they are unimportant, but because ranking them would produce misleading results. The remaining schools represent a reliable, nationally distributed sample.

**3. Three pillars of priority: Need, Impact, and Capacity Gap.** Academic need alone is insufficient for intervention targeting. A high-need school with 30 students represents a different resource allocation decision than one with 3,000. Similarly, a school in an LGU with ample education funding has different support needs than one in a fiscally constrained municipality. The priority score is the product of percentile ranks across all three pillars — ensuring that a school must score high on academic need, serve a substantial student population, *and* be located in an under-resourced LGU to reach the top of the list. This multiplicative design prevents any single factor from dominating.

**4. Robustness verification.** The Need pillar uses domain-informed weights to combine its six components (current level, trajectory, spread, and shape). To ensure the ranking is not an artifact of these specific weight choices, we test 500 random weight configurations drawn from a Dirichlet distribution. Result: 60% of ranked schools show near-zero rank volatility (IQR < 5 percentile points), and the top-100 intervention targets are stable across all tested scenarios. The main axis of sensitivity is the relative emphasis on current proficiency versus trajectory of change — not the inclusion of distributional measures.

## Why This Is Sustainable

The pipeline is designed around data DepEd already produces on a fixed schedule. When the next CRLA cycle completes (EoSY 2025-26), the new CSV is placed in the pipeline, a single entry is added to the time chain, and the system automatically produces updated progress scores, validation results, and priority rankings. No methodological changes are needed. No new instruments. No additional data collection burden on schools or divisions.

The chain-based design means that each new assessment cycle adds information without invalidating previous results. A school's Learning segment (BoSY → EoSY within one year) and Retention segment (EoSY → next BoSY) accumulate into a composite trajectory that grows more informative over time.

## What This Enables

For **division and regional offices**: a defensible, transparent basis for allocating reading intervention resources — one that accounts for academic need, student reach, and local fiscal capacity simultaneously.

For **central office planning**: a national view of where literacy gains are being made, where summer learning loss is most severe, and which schools consistently appear at the top of the priority list regardless of how the methodology is weighted.

For **monitoring and evaluation**: a built-in before-and-after framework. Schools that receive interventions can be tracked across subsequent CRLA cycles using the same pipeline, with the same validation standards, producing comparable progress scores.

---

*This framework was developed by the Center for Artificial Intelligence Research at De La Salle University in collaboration with the Department of Education. The full analytical pipeline, documentation, and reproducibility materials are available for review.*
