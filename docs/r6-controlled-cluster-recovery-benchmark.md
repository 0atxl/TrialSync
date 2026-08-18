# R6 controlled cluster-recovery benchmark contract

## Review and implementation status

The user accepted this one-run contract and authorized implementation on 2026-08-18. The local
generator, sealed answer-key boundary, label-free analysis, post-seal evaluator, and reduced-size
tests are implemented. The one allowed 750-member execution completed on 2026-08-18 and is now
sealed as the immutable benchmark result.

The benchmark is an R6 evaluation addendum, not a new phase. It does not create an R9.

## Research question

The accepted R6 V1 population did not produce robust density-separated groups, and the bounded V2
representation comparison did not pass its declared DBSCAN criteria. That result cannot by itself
distinguish between two explanations:

1. the accepted population contains overlapping continuous variation without strong global groups;
2. the representation or DBSCAN procedure cannot recover groups even when meaningful density
   structure exists.

This benchmark answers:

> When a separately generated patient population contains predeclared, overlapping latent groups,
> can the unchanged TrialSync patient-fact and screening-profile pipelines recover that structure
> without access to the hidden group assignments?

The hidden assignment is an evaluation answer key, not a patient fact or product label. It cannot
be used to construct vectors, select DBSCAN candidates, rank FAISS neighbors, or change eligibility.

## Relationship to V1 and V2

The benchmark preserves all existing decisions:

- the accepted V1 run remains immutable and active;
- V1 DBSCAN remains a limited baseline finding;
- the completed V2 representation comparison remains rejected under its frozen criteria;
- the active V1 FAISS indexes remain unchanged;
- the benchmark cannot become the active runtime cohort;
- no current artifact may be overwritten, reclassified, or removed.

The benchmark applies the already defined V1 and V2 feature transformations to a separate patient
population. It evaluates four spaces independently:

1. patient fact with the V1 transformation;
2. patient fact with the V2 transformation;
3. screening profile with the V1 transformation;
4. screening profile with the V2 transformation.

Each benchmark representation records both a benchmark identifier and its existing source feature
contract. Passing the benchmark does not retroactively promote V2 on the accepted V1 population.

## Fixed identifiers and dimensions

| Field | Frozen value |
|---|---|
| Benchmark contract | `r6-controlled-recovery-v1` |
| Generator contract | `r6-controlled-recovery-generator-v1` |
| Answer-key contract | `r6-controlled-recovery-answer-key-v1` |
| Evaluation contract | `r6-controlled-recovery-evaluation-v1` |
| Generation seed | `60817` |
| Independent runs | 1 |
| Screening date | `2026-08-16` |
| Patient snapshots | 750 |
| Structured-group members | 660 |
| Background members | 90 |
| Approved trial versions | the same frozen 20-version R6 V1 reference panel |
| Reference-panel checksum | `a9e0f6b06ce8c440f18f46d34217f0d642ecd4ea9b65a415111454963f1c686b` |
| Criterion-order checksum | `60825a8e975106d7a01558027a1407c57ebcc579db8b7c0c8f16f4bb00cab641` |
| Screening pairs | 15,000 |
| Expected criterion results | 60,000 |
| Compute path | local CPU only |

The benchmark makes no hosted model request and requires no provider credential, GPU, or external
patient record.

## Generation design

### Single-run rule

The benchmark uses one frozen 750-member population. Seed `60817` is selected before
implementation and cannot be replaced after generation because of an unfavorable result. Seeded
subsample and nearby-parameter checks provide within-population stability evidence; the final
report must state that the benchmark does not establish generation-seed generalization.

### Hidden assignment schedule

The answer key contains four structured groups and a heterogeneous background class. Group sizes
are deliberately unequal so recovery is not limited to four equally sized spheres.

| Hidden ID | Members | Intended joint pattern |
|---|---:|---|
| `latent_group_01` | 210 | type-2 glucose-regulation pattern with related measurements and medications |
| `latent_group_02` | 180 | blood-pressure and kidney-function pattern |
| `latent_group_03` | 150 | airway-condition pattern with comparatively lower metabolic burden |
| `latent_group_04` | 120 | type-1 glucose-management pattern |
| `background` | 90 | heterogeneous combinations, crossover records, and numeric edge cases |

These descriptions document generation assumptions only. They are not diagnoses, discovered
phenotypes, or patient-facing categories.

The generator constructs the exact assignment list, shuffles it using a dedicated assignment RNG
stream, and only then creates patient identifiers. Patient identifiers and neutral display labels
derive from the shuffled ordinal, seed, contract version, and fixed UUID namespace; they must not
contain or encode the hidden group ID. Final representation order remains the canonical sorted
patient-identifier order.

### RNG isolation

Generation uses deterministic named random streams for:

- assignment shuffle;
- demographics;
- condition truth;
- medication truth;
- observation values;
- missing and unknown states;
- evidence dates;
- background variation.

Each stream derives from the fixed seed, patient ordinal, and a documented numeric stream code.
Adding a future field must not shift draws for existing fields. The manifest records the RNG
algorithm, stream-code table, draw order within each field, and implementation-library versions.

The frozen algorithm is NumPy `Generator(PCG64)` with a separate `SeedSequence` built from
`[60817, patient_ordinal, stream_code]` for each patient-level stream. The assignment stream uses
patient ordinal zero. The implementation must freeze and record the NumPy version before the first
run. The UUID namespace is UUIDv5 of the URL-namespace value
`trialsync:r6:controlled-recovery:v1`; seed and shuffled ordinal, but never group identity, are
inputs to patient UUID generation.

### Demographic schema

Age distributions overlap intentionally. Ages use a truncated normal draw except for background
members, which use a discrete uniform draw.

| Hidden ID | Age mean | SD | Minimum | Maximum |
|---|---:|---:|---:|---:|
| `latent_group_01` | 58 | 11 | 32 | 82 |
| `latent_group_02` | 64 | 10 | 38 | 82 |
| `latent_group_03` | 38 | 13 | 18 | 70 |
| `latent_group_04` | 31 | 10 | 18 | 58 |
| `background` | uniform | — | 18 | 82 |

Every group uses the same sex probabilities: female `0.45`, male `0.45`, and unspecified `0.10`.
This prevents sex from becoming an answer-key shortcut. Date of birth derives from age plus a
uniform day offset and is valid relative to the fixed screening date.

### Condition-truth schema

Conditions are drawn from hidden truth states before observation-level missingness is applied.
Type-1 diabetes is drawn first; when present, type-2 diabetes is forced absent. All other draws are
conditionally independent given the hidden group and crossover rule.

| Hidden ID | Type 1 | Type 2 | Hypertension | Asthma |
|---|---:|---:|---:|---:|
| `latent_group_01` | 0.02 | 0.82 | 0.48 | 0.14 |
| `latent_group_02` | 0.03 | 0.28 | 0.86 | 0.12 |
| `latent_group_03` | 0.04 | 0.12 | 0.18 | 0.84 |
| `latent_group_04` | 0.84 | 0.02 | 0.18 | 0.14 |

For the 90 background members, the four condition states use broad independent draws with nominal
probabilities `0.12`, `0.25`, `0.38`, and `0.24`, subject to the same type-1/type-2 exclusion. Half
of the background members then receive one deterministically selected condition-state inversion.
This prevents the background class from becoming a fifth compact group.

The predeclared crossover counts are 25, 22, 18, and 14 members for groups 01 through 04,
respectively: 79 of 660 structured members. Members are selected with a dedicated per-group stream.
A crossover member draws one different structured group uniformly and blends primary and secondary
probabilities at `0.75 / 0.25`. Its answer-key assignment remains its primary group. Crossover
membership is stored only in the sealed generation audit, never in an analysis feature.

### Medication-truth schema

Medication states depend on the hidden condition truth rather than the visible assertion, so an
unknown or omitted condition fact does not erase the underlying correlation:

| Medication | Conditional probability |
|---|---|
| Metformin | `0.75` with type 2, otherwise `0.05` |
| Insulin | `0.88` with type 1; `0.22` with type 2; otherwise `0.03` |
| Semaglutide | `0.38` with type 2, otherwise `0.04` |
| Atorvastatin | `0.65` with hypertension, type 2, or age at least 55; otherwise `0.08` |

Background members blend each condition-dependent probability equally with an independent draw
from `Uniform(0.05, 0.70)`. This creates heterogeneous medication combinations without exposing a
background flag.

### Observation schema

All numeric observations use the existing R6 concepts, units, clipping bounds, and compatible
fact schema. A value is drawn from `Normal(center, spread)` and clipped only to the declared valid
range.

| Observation | Center formula before group residual | Spread | Valid range |
|---|---|---:|---|
| HbA1c (%) | `5.4 + 2.7*type1 + 2.3*type2` | 1.00 | 4.5–12.5 |
| Fasting glucose (mg/dL) | `92 + 72*type1 + 62*type2` | 26 | 65–280 |
| eGFR (mL/min/1.73m2) | `105 - 0.65*max(age-30,0) - 12*diabetes` | 13 | 25–125 |
| Creatinine (mg/dL) | `0.78 + 0.008*max(age-40,0) + 0.22*diabetes` | 0.22 | 0.5–2.8 |
| Hemoglobin (g/dL) | `13.8 - 0.45*diabetes` | 1.25 | 8.5–17.5 |
| Platelets (10^9/L) | `245` | 58 | 90–520 |
| BMI (kg/m2) | `24 + 5.0*type2 + 1.8*hypertension` | 3.8 | 16–48 |
| Systolic BP (mmHg) | `112 + 0.25*max(age-30,0) + 22*hypertension` | 13 | 85–210 |
| Diastolic BP (mmHg) | `72 + 12*hypertension` | 8.5 | 50–125 |
| Potassium (mmol/L) | `4.2` | 0.42 | 2.8–6.2 |

`diabetes` equals one when either type-1 or type-2 truth is present. Structured groups apply these
additional residuals before sampling:

| Hidden ID | Residual adjustments |
|---|---|
| `latent_group_01` | HbA1c `+0.4`, fasting glucose `+15`, BMI `+2.0`, eGFR `-5` |
| `latent_group_02` | systolic BP `+10`, diastolic BP `+6`, eGFR `-12`, creatinine `+0.20` |
| `latent_group_03` | no added numeric residual; separation must not depend on an invented biomarker |
| `latent_group_04` | HbA1c `+0.5`, fasting glucose `+18`, BMI `-1.5` |

Crossover members use the same `0.75 / 0.25` blend for residuals. Background members start from
the condition-based center, add one independently selected residual from `-1.5` to `+1.5` spreads
for each observation, and use `1.35` times the declared spread. This creates broad edge and bridge
records rather than a compact background center.

### Missingness, assertions, and dates

Missingness is identical across the four structured groups so it cannot reveal the answer key:

| Fact category | Omitted | Recorded `unknown` | Recorded present/absent or numeric |
|---|---:|---:|---:|
| Condition and medication | 0.08 | 0.06 | 0.86 |
| Observation | 0.12 | 0.05 | 0.83 |

Background members use the same rates. A missing fact is absent from the fact table; `unknown` is
an explicit assertion with no invented numeric value. Missing values are never converted to zero.
Effective dates use independent uniform offsets of 1–90 days for condition/medication facts and
1–150 days for observations. All facts retain current temporality and neutral source provenance.

## Materialization and generation schema

### Directory boundary

The future implementation must write only beneath:

```text
artifacts/r6/controlled-recovery/<run_id>/
  cohort/                    # label-free source tables and manifest
  answer-key/                # local-only hidden assignments and generation audit
  analysis/                  # label-free representations, DBSCAN, projections, and indexes
  evaluation/                # post-seal recovery metrics and decision
```

The complete directory remains excluded from Git. A later summary report may be committed after
review, but no patient row or answer-key row belongs in the repository.

### Label-free cohort files

The `cohort/` directory reuses the accepted R6 table contracts:

| File | Cardinality | Required identity/linkage |
|---|---:|---|
| `patients.parquet` | 750 | unique snapshot ID/version, neutral label, date of birth |
| `patient_facts.parquet` | variable | unique fact ID linked to one snapshot; type, concept, value, unit, assertion, temporality, effective date, source |
| `reference_panel.json` | 20 versions | byte/semantic equivalence to the accepted V1 panel |
| `screening_pairs.parquet` | 15,000 | one unique patient × trial-version pair and canonical overall result |
| `criterion_results.parquet` | 60,000 | one result per pair × ordered criterion with reason, evidence, rejected evidence, and missing requirements |
| `generation_config.json` | one object | every distribution, RNG stream, seed, version, count, and checksum declared here |
| `manifest.json` | one object | run metadata, counts, semantic checksums, and per-file hashes |

The exact pure single-screening engine evaluates every patient against the same frozen 20-version
panel. The 15,000 evaluations collapse to exactly 750 representation rows. Ordinary saved
screening history and PostgreSQL remain untouched.

### Sealed answer-key files

`answer-key/answer_key.parquet` has exactly 750 rows and only these fields:

| Field | Type | Rule |
|---|---|---|
| `patient_snapshot_id` | UUID string | unique and present in `patients.parquet` |
| `latent_group_id` | enum string | `latent_group_01`–`latent_group_04` or `background` |
| `is_background` | boolean | true only when `latent_group_id == background` |
| `answer_key_version` | string | exactly `r6-controlled-recovery-answer-key-v1` |

`answer-key/generation_audit.parquet` may additionally record crossover membership, secondary
group, latent truth states, background perturbations, and named RNG draw identifiers. It exists
only to reproduce and audit generation. Neither answer-key file may be accepted by a
representation builder or runtime artifact loader.

`answer-key/manifest.json` records row counts, semantic checksums, and file hashes. The label-free
cohort manifest records only the answer-key manifest hash, not its rows or relative path.

### Manifest requirements

Every stage has its own immutable manifest; no sealed manifest is edited in place:

- `cohort/manifest.json` records the run ID, path validation, contract versions, seed, screening
  date, generation timestamp, UUID namespace, RNG details, source counts, engine/DSL/terminology/unit
  versions, source semantic checksums, file hashes, and answer-key-manifest hash;
- `answer-key/manifest.json` records its contract, patient and group counts, cohort semantic
  checksum, answer-key and audit hashes, and no analysis outcome;
- `analysis/manifest.json` references the cohort-manifest hash and records every representation,
  preprocessing, subject order, feature order, DBSCAN, K-means, projection, index, verification,
  and output-file checksum; its canonical hash is the analysis seal;
- `evaluation/manifest.json` references the analysis seal and answer-key-manifest hash, records all
  post-reveal metrics and pass/fail decisions, and sets `activation_changed: false`.

The evaluation stage must refuse a mismatched or altered predecessor manifest. A failed stage
writes a separate failure record and does not modify any earlier manifest.

## Leakage and execution boundary

The benchmark uses four ordered stages:

1. **Generate:** create the label-free cohort and separately sealed answer key.
2. **Analyze:** build all four representations, select DBSCAN candidates, produce the K-means
   diagnostic, build FAISS indexes, and seal all label-free outputs by hash.
3. **Reveal:** load the sealed answer key only after the analysis seal exists and matches.
4. **Evaluate:** calculate recovery metrics without changing any representation, parameter,
   cluster label, or neighbor list.

The analysis command receives the `cohort/` path only. The evaluator receives the immutable
analysis seal plus the answer-key manifest. Code that imports or parses the answer key must live in
the evaluator boundary and must not be imported by representation, DBSCAN, FAISS, API, or frontend
modules.

The following fields and tokens are prohibited from patient facts, screening records, feature
names, vector metadata, indexes, cluster selection, APIs, and frontend payloads:

- latent group or secondary group;
- background/noise truth;
- crossover membership;
- generator stream, draw, probability, or residual identifier;
- answer-key version or assignment order;
- dropout outcome, risk, SHAP, chat, or RAG information.

Automated leakage tests must recursively inspect serialized column names, feature names, metadata,
and API schemas and fail closed when a prohibited source is found.

## Frozen unsupervised analysis protocol

### Representations

Build the V1 and V2 patient-fact and screening-profile representations without changing their
feature meaning. The benchmark wrapper records these identities:

| Benchmark representation | Source feature contract |
|---|---|
| `r6.recovery.patient_fact.v1` | `r6.patient_fact.v1` |
| `r6.recovery.patient_fact.v2` | `r6.patient_fact.v2` |
| `r6.recovery.screening_profile.v1` | `r6.screening_profile.v1` |
| `r6.recovery.screening_profile.v2` | `r6.screening_profile.v2` |

Member order and raw feature meanings must match between V1 and V2 within each representation.
Zero-variance removal and fitted preprocessing statistics remain fully recorded. PCA remains a
two-dimensional display diagnostic and is never used for clustering or neighbor retrieval.

### Scale-adaptive DBSCAN grid

The V2 comparison intentionally reused the V1 absolute radius grid. This benchmark instead tests
recovery using a predeclared scale-adaptive grid so representation-scale changes do not determine
the result.

For each representation and each `min_samples` value in `5, 10, 15, 20`:

1. compute every member's Euclidean distance to its (`min_samples - 1`)-th nearest other member in
   the full L2-normalized feature space, because DBSCAN counts the member itself in `min_samples`;
2. calculate quantiles `0.50, 0.65, 0.80, 0.90, 0.95` of that distance distribution;
3. round each radius to six decimal places;
4. evaluate the resulting 20 `(eps, min_samples)` pairs exactly once.

No answer-key field may influence the grid. Duplicate candidate pairs after rounding are evaluated
once and recorded as duplicates in metadata.

Each candidate receives:

- cluster count, sizes, core count, and noise fraction;
- silhouette when mathematically defined;
- five seeded 80% subsample ARI checks;
- nearby-parameter checks at radius `-5%` and `+5%` and `min_samples - 1` and `+1`;
- full labels in canonical member order.

Before answer-key reveal, candidate selection first requires:

- three to five non-noise clusters;
- noise from 5% through 35%;
- smallest cluster at least 5% of assigned members;
- largest cluster no more than 50% of assigned members.

Eligible candidates are ranked lexicographically by subsample ARI, nearby-parameter ARI,
silhouette, lower noise, smaller radius, and smaller `min_samples`. If none pass the structural
filter, the report records no selected recovery candidate; it must not relax the filter after
answer-key reveal.

### K-means diagnostic

As a non-activating comparison, evaluate K-means for `k=2` through `k=6` using random state
`20260816` and 20 initializations. Record silhouette, Davies–Bouldin score, cluster sizes, and
post-reveal ARI. K-means cannot replace DBSCAN or satisfy the DBSCAN recovery decision; it only
helps distinguish absent density structure from a centroid-shaped partition.

### Exact FAISS evaluation

Build one CPU `IndexFlatIP` index per benchmark representation over normalized `float32` vectors:
four indexes in total. Before reveal, every index must:

- contain exactly 750 vectors in the recorded member order;
- exclude self matches;
- return ten neighbors per query;
- match brute-force cosine neighbors and scores for all 750 members;
- preserve deterministic tie ordering;
- reject representation, cohort, panel, feature-order, or subject-order mismatch.

After reveal, calculate same-group precision at 10 for the 660 structured members, macro precision
across the four groups, top-1 same-group rate, and lift over the exact size-weighted all-member
baseline. Background queries are excluded from the primary precision measure and reported
separately with neighbor-group entropy and background-neighbor rate. Existing semantic condition,
demographic, criterion-state, and overall-trial agreement measures remain descriptive diagnostics.

## Acceptance criteria

Integrity is mandatory:

- all counts, links, engine results, checksums, and analysis-seal hashes pass;
- all four representations contain exactly 750 unique members;
- prohibited-field leakage checks pass;
- missing and `unknown` states remain explicit;
- the answer key is not opened before analysis sealing;
- all four FAISS indexes pass 750-member brute-force verification;
- activation remains unchanged.

A representation passes **DBSCAN controlled recovery** only when its sealed selected candidate
satisfies all of:

| Measure | Threshold |
|---|---:|
| Non-noise clusters | 3–5 |
| Noise fraction | 5%–30% |
| Smallest cluster | at least 5% of assigned members |
| Largest cluster | at most 45% of assigned members |
| Silhouette | at least 0.10 |
| Seeded subsample ARI | at least 0.70 |
| Nearby-parameter ARI | at least 0.70 |
| All-member ARI versus hidden assignment | at least 0.60 |
| Structured-member ARI | at least 0.65 |
| Background/noise F1 | at least 0.50 |

A representation passes **FAISS controlled recovery** only when:

- structured-member precision@10 is at least `0.70`;
- macro group precision@10 is at least `0.60`;
- precision@10 is at least `2.5` times its exact size-weighted baseline;
- every exact-index integrity check passes.

Patient-fact and screening-profile spaces pass or fail independently. The benchmark establishes
that the core clustering pipeline can recover known structure when at least one patient-fact
transformation passes DBSCAN controlled recovery. Screening-profile recovery is a separate test of
whether the deterministic trial panel preserves that structure. FAISS success never substitutes
for DBSCAN success.

The contract hash freezes the seed, distributions, thresholds, and decision rules before the full
750-member generation. A failed benchmark is reported as a failure and may lead to a separately
reviewed future protocol, not a replacement seed or edited result. If a genuine implementation
defect is discovered after the full run begins, the run is invalidated and a corrected contract
version is required before regeneration.

## Interpretation matrix

| Result | Supported interpretation |
|---|---|
| Patient-fact DBSCAN passes | The pipeline can recover predeclared patient structure; weak V1 clustering is primarily population-specific |
| Patient-fact DBSCAN fails and K-means passes | Broad centroid structure exists, but DBSCAN density assumptions or parameterization are unsuitable |
| Both DBSCAN and K-means fail | The feature transformation does not preserve even the controlled structure strongly enough |
| Patient-fact passes; screening profile fails | Deterministic screening patterns do not preserve the patient-fact groups across this trial panel |
| FAISS passes while DBSCAN fails | Local same-group retrieval works without reliable global density partitions |
| V2 passes where V1 fails | Block balancing helps recovery on the controlled population but does not change the rejected V2 result on the accepted population |

No outcome supports a real-world phenotype, diagnosis, treatment, eligibility, or deployment claim.

## Required review output

After execution, one report must include:

- the frozen contract hash and implementation commit;
- all generation and semantic checksums;
- group counts and post-reveal descriptive summaries;
- complete DBSCAN candidate tables for all four representations;
- selected-candidate internal metrics and hidden-label recovery metrics;
- K-means diagnostic tables;
- all four exact-index verifications and FAISS recovery metrics;
- a leakage audit;
- a decision for every representation;
- an explicit statement that V1 activation did not change.

## Observed single-run outcome

The frozen run `r6-recovery-9023c03a-30d8-5665-9016-ef8b537e29d0` completed on 2026-08-18.
All predecessor seals, leakage checks, member counts, missing-state checks, and four exact
FAISS/brute-force audits passed. The active V1 setting remained unchanged.

No representation produced a DBSCAN candidate that met the label-free structural filter, so no
hidden-label DBSCAN recovery metric was eligible for reporting. K-means was retained as the
non-activating diagnostic:

| Representation | Best structured K-means ARI | Highest silhouette | FAISS structured precision@10 | FAISS macro precision@10 | FAISS lift |
|---|---:|---:|---:|---:|---:|
| Patient fact V1 | 0.433 (k=4) | 0.050 | 0.480 | 0.486 | 2.11× |
| Patient fact V2 | 0.249 (k=3) | 0.080 | 0.583 | 0.590 | 2.56× |
| Screening profile V1 | 0.059 (k=6) | 0.137 | 0.506 | 0.510 | 2.22× |
| Screening profile V2 | 0.096 (k=6) | 0.222 | 0.481 | 0.479 | 2.11× |

Patient-fact V2 therefore shows moderate local same-group retrieval, but it misses the frozen
FAISS thresholds of `0.70` structured precision and `0.60` macro precision. Its lift exceeds the
`2.5×` threshold, but that criterion alone is insufficient. All other FAISS spaces miss at least
one primary threshold as well.

The controlled-recovery decision is **failed**. The result supports this bounded interpretation:
the exact indexing and evaluation machinery is functioning, and the patient-fact V2 space retains
some local group signal, but neither approved patient-fact transformation produced sufficiently
separated global density structure or sufficiently pure local neighborhoods for the frozen
recovery claim. The screening-profile spaces preserve even less of the hidden grouping. The result
does not justify changing the seed, relaxing thresholds, activating a benchmark cohort, or making
clinical phenotype claims.

This is the final result for the one-run addendum. Any future positive-control design requires a
new reviewed contract version; the completed run must remain immutable.

## Execution sequence

Install the already approved R6 dependency set, then run the three stages from the repository
root. Use the run directory printed by the first command in the next two commands:

```bash
backend/.venv/bin/pip install --editable './backend[dev,research-r6]'
backend/.venv/bin/python -m research.build_r6_recovery \
  --output-root artifacts/r6/controlled-recovery
backend/.venv/bin/python -m research.analyze_r6_recovery \
  --cohort-directory artifacts/r6/controlled-recovery/<run_id>/cohort
backend/.venv/bin/python -m research.evaluate_r6_recovery \
  --run-directory artifacts/r6/controlled-recovery/<run_id>
```

Generation, analysis, and evaluation are individually one-shot and refuse to replace an existing
stage. The analysis command receives only the `cohort/` path; its implementation does not import or
parse the answer-key artifact. Evaluation verifies both predecessor seals before opening the key.
None of these commands changes `TRIALSYNC_RESEARCH_COHORT_ACTIVE_RUN`.

The full-run output above is the review record. Do not change the seed, distributions,
representation, grid, selection rule, or threshold after seeing the result. A genuine
implementation defect would invalidate the run and require a separately reviewed contract version.
