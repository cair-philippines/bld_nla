# How We Identify Schools That Need Help

## What is this document?

This document explains how we determine which public elementary schools should be prioritized for reading interventions. It describes the method behind the priority list produced by the CRLA (Classroom Reading Level Assessment) analysis pipeline. The list is not a judgment of schools — it is a tool for directing limited resources where they can do the most good.

## How do we measure reading?

Every school year, DepEd administers the CRLA to all Grades 1–3 students in public elementary schools. Each student is classified into one of five reading levels:

| Level | What it means |
|-------|---------------|
| **Lower Emergent** | The student is just beginning to recognize letters and sounds |
| **Higher Emergent** | The student can recognize some words but struggles with sentences |
| **Developing** | The student can read simple sentences but not yet fluently |
| **Transitioning** | The student reads with some fluency but still needs support |
| **Grade Level** | The student reads at the expected level for their grade |

We convert these five levels into a simple number from 1 to 5, where 1 means Lower Emergent and 5 means Grade Level. A school's **reading score** is the average across all its students and all assessed grade-language groups (Grade 1, Grade 2 Mother Tongue, Grade 2 Filipino, Grade 3 Mother Tongue, Grade 3 Filipino, Grade 3 English).

A school with a score of **4.2** means the average student is reading above the Transitioning level — close to Grade Level. A school with a score of **2.8** means the average student is between Higher Emergent and Developing — significantly below where they should be.

We compute this score at the beginning of each school year (BoSY) and at the end (EoSY). The difference tells us whether students improved during the school year. We currently use two complete school years: **SY 2024-25** and **SY 2025-26**.

## How do we decide which schools need help?

Think of it like a hospital emergency room. Doctors do not see patients first-come-first-served. They use **triage** — a system that considers three things at once:

1. **How serious is the patient's condition?**
2. **How many patients are affected?**
3. **Can the local clinic handle it, or do they need outside help?**

We apply the same logic to schools. We ask three questions — and a school must score high on **all three** to reach the top of the priority list. Scoring high on just one is not enough.

### Question 1: How much do the students need help? (Need)

This looks at two things:

- **Where are the students now?** A school where the average student is at Higher Emergent (score of 2.0) needs more help than one where the average is at Transitioning (score of 4.0).

- **Are they getting better or worse?** We compare BoSY to EoSY within the same school year. A school where students improved by +1.2 levels is in a different situation from one where students only improved by +0.1 — or declined.

We look at both school years (SY 2024-25 and SY 2025-26) and take the average improvement across both. A school that showed little improvement in both years has a consistently high need — it is not a one-time dip.

We also consider whether students are spread out across many levels (high inequality within the school) or clustered together. A school where half the students are at Grade Level and the other half are at Lower Emergent has a different kind of problem than a school where everyone is at Developing.

### Question 2: How many students would benefit? (Impact)

A school with 1,200 assessed students represents a larger opportunity for impact than a school with 80 students. Both may need help, but intervening in the larger school reaches more learners per intervention.

This is measured simply: the total number of assessed Grades 1–3 students at the end of the most recent school year (EoSY 2025-26).

### Question 3: Can the local government support the school? (Capacity Gap)

Every LGU (city or municipality) collects a **Special Education Fund (SEF)** as part of its Real Property Tax. This fund is earmarked for education. Some LGUs collect a lot per student; others collect very little.

We compute the **SEF per student** for each LGU — the total SEF divided by the total number of enrolled public school students in that LGU. A lower amount means the LGU has fewer resources available per student and may struggle to fund interventions on its own.

A school in an LGU with SEF of PHP 23 per student has a much larger capacity gap than one with PHP 2,100 per student.

## How does the final score work?

Each school gets a score for Need, Impact, and Capacity Gap. We convert each score into a **ranking** — what percentage of schools does this school score higher than? This is the percentile. A school at the 95th percentile for Need means it has higher need than 95% of all ranked schools.

The final priority score is the combination of all three percentiles. The key rule is:

> **A school must rank high on all three dimensions to reach the top of the list.**

A school with extremely high Need but very few students and a well-funded LGU will rank in the middle — not the top. A school with many students but strong reading scores will also rank in the middle. Only schools that are struggling, large, and under-resourced rise to the top.

## A tale of two schools

To make this concrete, here are two real schools from the ranking.

### Sibuco Central School — Rank 1 (Top 1%)

Sibuco CS is in Sibuco, Zamboanga del Norte (Region IX). At the end of SY 2025-26, its average reading score was **2.80** — most students are between Higher Emergent and Developing. Over two school years, students improved only modestly: +0.37 levels in SY 2024-25 and +0.85 in SY 2025-26. There are **1,223 assessed students**. The municipality of Sibuco spends only **PHP 23 per student** from its Special Education Fund — one of the lowest in the country.

Sibuco CS ranks at the top because it checks all three boxes: students are struggling (Need: 99th percentile), there are many of them (Impact: 96th percentile), and the local government has almost no capacity to help (Capacity Gap: 100th percentile).

### Tagaytay Elementary School — Rank 8,383 (50th percentile)

Tagaytay ES is in Kananga, Leyte (Region VIII). At the end of SY 2025-26, its average reading score was **4.33** — students are above Transitioning, close to Grade Level. In SY 2024-25 there was zero improvement, but in SY 2025-26 students improved by +1.07 levels. There are **244 assessed students**. The municipality of Kananga spends **PHP 1,327 per student** — well above the national median.

Tagaytay ES has moderate need (74th percentile) — the flat year in SY 2024-25 is concerning. But it has only moderate impact (60th percentile) due to its smaller size, and its LGU is relatively well-funded (only 15th percentile for Capacity Gap). It lands in the middle of the ranking — not ignored, but not the most urgent.

### Why does Sibuco rank higher?

Not because one number is bigger. Because **all three dimensions point the same direction**: high need, high impact, low local capacity. Tagaytay ES has a concerning trajectory in one year, but its students are mostly reading well, and its LGU has resources to respond. The priority list reflects this difference.

## Why are some schools not on the list?

Out of approximately 39,000 schools in the CRLA dataset, about 16,800 appear in the composite ranking. The rest are excluded — not because they are unimportant, but because we do not have enough data to rank them confidently.

To be ranked, a school must meet all of the following in **both** SY 2024-25 and SY 2025-26:

- **Assessed all three grade levels** (Grades 1, 2, and 3)
- **At least 4 of 6 grade-language groups** have data (e.g., G1, G2 MT, G2 Fil, G3 Eng)
- **At least 15 students assessed** in every reporting group
- **Student count is stable** between BoSY and EoSY (no more than 25% change)

These checks guard against ranking a school based on incomplete or unreliable data. A school that only assessed Grade 1 students, or one where only 8 students were tested in a group, would produce a misleading score. We would rather leave a school unranked than rank it incorrectly.

Schools that fail these checks in one year but pass in the other are still excluded from the composite ranking — we need consistent data across both years to make a fair comparison.

## How do we know the ranking is fair?

The Need score uses a set of weights to balance current reading levels against improvement trajectory. These weights are based on expert judgment — for example, we weigh current proficiency level and trajectory equally because a school that is both low-performing and not improving needs more urgent attention.

To test whether the ranking depends too heavily on any one weight choice, we ran **500 different weight configurations** — randomly varying how much emphasis is placed on each factor. The result: **60% of schools showed almost no change in their ranking** across all 500 configurations, and the top 100 schools were remarkably stable. This means the ranking reflects a genuine pattern in the data, not an artifact of one particular weighting decision.

## Common questions

**Why do you use two school years instead of one?**
Using two years tells us whether a school's situation is persistent or temporary. A school that struggled in both SY 2024-25 and SY 2025-26 has a deeper problem than one that had a bad year followed by a good one. The ranking averages both years so that consistent underperformance is weighted appropriately.

**My school has low scores but is not on the list. Why?**
Most likely, the school did not meet the data completeness requirements in one or both school years. Check the Reference sheet in the Excel file — it shows every school's validity status and the specific reason for exclusion.

**Will the list change when new data comes in?**
Yes. When new CRLA data is submitted, the pipeline can be re-run to produce an updated ranking. Schools that were previously excluded due to incomplete data may enter the ranking once their data is complete.

**What happens after a school is identified?**
The priority list is an input to decision-making, not the final decision. SDOs and Regional Offices use this list alongside their local knowledge to allocate reading intervention resources. The list helps ensure that allocation decisions are grounded in data, but it does not replace professional judgment about what specific interventions each school needs.

**What about the 131 schools from the first cycle?**
An earlier round of school selection identified 131 schools for intervention. These schools appear in the full ranking (tagged as "1st Cycle") but are excluded from the Top 100 list to avoid double-allocating resources. Of the 131, 47 passed the data quality checks for both school years and appear in the ranked list.
