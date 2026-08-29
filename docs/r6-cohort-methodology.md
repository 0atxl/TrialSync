# R6 cohort methodology and experiment evolution

This reading material explains how the R6 cohort, DBSCAN discovery, and FAISS similarity work; why the earlier cohort experiments were weak; and why the accepted V3 run is a controlled positive-control result. It is a description of a versioned project experiment, not a claim that the groups are real-world clinical phenotypes.

The executable configuration is [`backend/research/configs/r6_v3.py`](../backend/research/configs/r6_v3.py). Every materialized run also writes a complete `generation_config.json`, semantic checksums, implementation checksums, a public manifest, and a separately sealed evaluation answer key. The [V3 controlled-cohort contract](r6-v3-controlled-cohort.md) remains the authoritative runtime and seal specification.

## What R6 analyzes

R6 starts with **750 unique immutable patient snapshots**, not 15,000 samples. Each snapshot is evaluated by the unchanged deterministic screening engine against **20 fixed approved trial versions**.

| Artifact | Count | Purpose |
|---|---:|---|
| Patient snapshots | 750 | One patient-level member per cohort row |
| Approved reference-trial versions | 20 | Fixed panel used for every member |
| Patient × trial screening pairs | 15,000 | Deterministic evaluation matrix, not cohort rows |
| Criterion results | 60,000 | Evidence-pattern input for screening-profile features |
| Patient-fact matrix | 750 × 97 | Intrinsic recorded-fact representation |
| Screening-profile matrix | 750 × 314 | Eligibility-evidence-pattern representation |

The patient-fact representation captures demographics, condition and medication states, measurements, missingness, and evidence age. The screening-profile representation captures pass/fail/unknown criterion states, result rates, missing-information categories, and patterns across the fixed panel. Neither includes dropout outcomes, risk probabilities, SHAP values, chat text, retrieval output, or the hidden V3 group assignment.

## Fixed analysis pipeline

All variants use the same downstream analysis boundary:

1. Select the latest current fact for each concept.
2. Encode condition and medication state as `present`, `absent`, `unknown`, and `missing` features. Unknown is never halfway between pass and fail.
3. Encode observation values plus value-missing indicators, and evidence age plus evidence-age-missing indicators.
4. Median-impute only declared numeric values, standardize every feature, then L2-normalize each vector.
5. Run DBSCAN in the full 97D or 314D normalized space. The seeded 2D PCA projection is display only.
6. Build one CPU `faiss.IndexFlatIP` index per representation. Inner product on unit vectors is exact cosine similarity.

The DBSCAN grid was declared before V3:

| Setting | Fixed value |
|---|---|
| `eps` candidates | `0.45`, `0.60`, `0.75`, `0.90`, `1.05`, `1.20` |
| `min_samples` candidates | `5`, `10`, `15`, `20` |
| Bootstrap repeats | 5 |
| Bootstrap member fraction | 80% |
| Nearby sensitivity checks | `eps × 0.95`, `eps × 1.05`, `min_samples ± 1` |
| Selection order | Non-trivial groups, bootstrap ARI, nearby-parameter ARI, silhouette, then noise |
| Noise preference | Multi-group candidates with at most 50% noise when available |

All-noise and one-group outcomes can look perfectly stable because every rerun produces the same trivial labels. They are reported but cannot outrank a non-trivial partition merely because their adjusted-rand score is high.

## Why V1 and V2 were weak

V1 generated facts through mostly independent probability draws. A condition could appear without the full age, medication, laboratory, and timing pattern that would make the member consistently similar to a particular population. Observation values had broad overlapping distributions and facts received independently varying effective dates.

This formed a high-dimensional **continuum**: many members differed slightly, but there were few compact islands separated by low-density gaps. In a 97-dimensional normalized space, unrelated variation consumes distance while common structure becomes harder for one DBSCAN radius to distinguish. Independent fact dates were especially unhelpful because evidence-age dimensions changed without describing a coherent encounter.

The screening-profile space had a second problem. Much of the fixed panel produced similar ineligibility patterns, so many criterion-state columns were correlated or dominated by the same broad result. That reduced density contrast.

| Variant | Patient-fact outcome | Screening-profile outcome | Interpretation |
|---|---|---|---|
| V1 baseline | Approximate silhouette `-0.05`; unstable or skewed local groups | Silhouette close to `0`; overlapping profiles | The population was not density-separated in the frozen spaces |
| V2 feature reweighting | Two-group collapse; largest group about 99%; silhouette `0.0466` | One-group collapse; silhouette not meaningful | Weighting cannot create missing population structure |
| Controlled recovery | No candidate passed the declared multi-metric DBSCAN filter | No candidate passed the declared multi-metric filter | Small planted shifts remained weak relative to within-group variation and dimensional dilution |

Silhouette compares a member's average distance to its assigned group with its average distance to the nearest other group. Values near `1` indicate separation, values near `0` indicate overlap, and negative values mean a member may be closer to another group. It is calculated only for non-noise members when there are at least two assigned groups.

The weak V1/V2 result showed that DBSCAN was honestly reporting the supplied geometry. FAISS remained correct because exact nearest-neighbor retrieval does not require DBSCAN groups to exist.

## V3: changing the input geometry, not the algorithm

V3 was a controlled positive-control population redesign. It held the feature builders, fixed 20-trial panel, deterministic engine, DBSCAN grid, stability protocol, PCA display, and FAISS indexer unchanged. The independent variable was the patient population.

Instead of independently sampled facts, V3 generates coherent bundles: age, conditions, medications, laboratory observations, and encounter timing are drawn together. This creates dense regions in the same frozen feature spaces while retaining within-group variation. A broad background population tests DBSCAN's ability to leave members as noise instead of forcing every member into a group.

### Frozen V3 settings

| Setting | Value |
|---|---|
| Contract | `r6-cohort-v3` |
| Generator | `r6-controlled-groups-v3.1` |
| Seed | `60818` |
| Screening date | `2026-08-16` |
| Accepted runtime run | `r6-v3-6091f06c-542d-5b00-8bdc-6fbd782c9510` |
| Conditions | Type 1 diabetes, type 2 diabetes, hypertension, asthma |
| Medications | Metformin, atorvastatin, insulin, semaglutide |
| Observations | HbA1c, fasting glucose, eGFR, creatinine, hemoglobin, platelets, BMI, systolic/diastolic BP, potassium |

### The 750-member population

| Controlled group | Members | Age range | Condition/medication bundle | Main observation pattern |
|---|---:|---:|---|---|
| `young_t1d` | 160 | 18–32 | Type 1 diabetes and insulin | Higher HbA1c/glucose, lean BMI, preserved renal measures |
| `elderly_t2d` | 160 | 55–78 | Type 2 diabetes, metformin, mostly atorvastatin and semaglutide | Higher HbA1c/glucose, high BMI, older age |
| `hypertensive_renal` | 160 | 50–74 | Hypertension, mostly atorvastatin | High BP/creatinine/potassium and low eGFR |
| `respiratory_asthma` | 160 | 30–52 | Asthma without the metabolic medication bundle | Normal metabolic/renal pattern with elevated platelet centre |
| `healthy_borderline` background | 110 | 18–82 | Low independent condition/medication probabilities | Broad observation variation and more incomplete evidence |

The four structured groups have 1% skipped and 1% unknown condition, medication, and observation states. The background group has 8% skipped and 6% unknown condition/medication states, plus 10% skipped and 5% unknown observations. This is deliberate and disclosed: explicit missing-state features help make the background sparse, so background/noise performance is evaluated rather than described as independently discovered structure.

For every member, the generator deterministically shuffles the group assignments with the frozen seed; samples age within that group's range and recorded sex; creates one encounter date 14–45 days before screening; applies only 0–2 days of fact jitter around that encounter; samples observations from that group's declared Gaussian centres and spreads; clamps them to documented bounds; then creates the immutable snapshot. Each snapshot is evaluated against every reference trial, and checks enforce that the matrix still collapses to exactly 750 unique members.

The complete per-observation centres and standard deviations are serialized in each run's `generation_config.json`. The essential geometry change was the *relationship* between features. For example, the type-2 group jointly has older age, type-2 diabetes, metformin, high glucose/HbA1c, and high BMI, rather than receiving each independently.

## What V3 established

The evaluator uses the sealed group assignment only **after** DBSCAN and FAISS complete. It is not imported by feature construction, parameter selection, index construction, runtime queries, or API responses. This measures whether the frozen pipeline recovered deliberately present structure without leaking the answer into analysis.

| Measure | Patient-fact representation | Screening-profile representation |
|---|---:|---:|
| Selected DBSCAN parameters | `eps=0.60`, `min_samples=10` | `eps=0.60`, `min_samples=10` |
| DBSCAN groups | 4 | 11 eligibility-evidence profiles |
| Silhouette | `0.4042` | `0.8923` |
| Bootstrap ARI | `0.9990` | `0.9889` |
| Nearby-parameter ARI | `0.9805` | `0.9815` |
| Assigned members | 465 (62.0%) | 508 (67.7%) |
| Noise fraction | 38.0% | 32.3% |
| Weighted assignment purity | 100.0% | 99.2% |
| Background-to-noise recall | 100.0% | 96.4% |

Purity is reported with coverage. The patient-fact groups are pure among 465 assigned members, but DBSCAN treats 285 members as noise; it does not claim to recover every member. That is intended DBSCAN behaviour for ambiguous or sparse points.

Both FAISS indexes are exact `IndexFlatIP` indexes over normalized `float32` vectors. Every one of the 750 queries in each representation was compared with brute-force NumPy cosine search: **0 mismatches** outside the defined floating-point tie tolerance. Top-10 same-group precision among structured members was 92.2% in patient-fact space and 92.0% in screening-profile space—over 4.3 times the size-weighted baseline. This verifies retrieval in the controlled feature space; it does not make a neighbor an eligibility rationale or care instruction.

## Correct presentation statement

> The initial population did not contain sufficient density-separated structure for DBSCAN in the frozen feature spaces. After a controlled cohort redesign that created correlated patient profiles while keeping the screening engine, features, DBSCAN protocol, and exact FAISS indexes fixed, the pipeline reliably recovered the deliberately present structure and left broad background members as noise.

Do not say that R6 discovered real disease phenotypes, predicts outcomes, or uses similarity as eligibility evidence. DBSCAN is exploratory population grouping; FAISS is exact nearest-neighbor retrieval. Both are separate from deterministic eligibility and R5 dropout prediction.
