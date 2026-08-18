# R6 V2 representation experiment protocol

## Decision

The accepted R6 V1 run remains the immutable baseline. V2 is a bounded representation experiment
over the same source cohort; it is not a new patient generation, reference-panel selection, or
DBSCAN parameter search.

V2 was authorized after inspecting the complete V1 geometry. The purpose is to test whether
transparent feature balancing produces more coherent density structure without planting cluster
labels or tuning the cohort to obtain attractive metrics.

## Frozen inputs

V2 must reuse these accepted V1 inputs unchanged:

| Input | Frozen value |
|---|---|
| Run ID | `r6-c21e487e-3b0d-5562-b7ad-3c7e7bbfdf2f` |
| Patients | 750 immutable snapshots |
| Reference panel | 20 approved trial versions |
| Screening pairs | 15,000 |
| Criterion results | 60,000 |
| Cohort checksum | `77d3ef0f289aec1402c84e1f771fe80f3a8c4e843c3981069905da56c78f68a2` |
| Reference-panel checksum | `a9e0f6b06ce8c440f18f46d34217f0d642ecd4ea9b65a415111454963f1c686b` |
| Criterion-order checksum | `60825a8e975106d7a01558027a1407c57ebcc579db8b7c0c8f16f4bb00cab641` |

No patient facts, trial rules, criterion results, or source-table rows may be regenerated or
edited for V2. Dropout outcomes, dropout risk, SHAP, chat, RAG output, and generator-control fields
remain excluded.

## Why V2 is justified

V1 is reproducible and technically valid, but the selected DBSCAN partitions have weak separation:

| Diagnostic | Patient fact V1 | Screening profile V1 |
|---|---:|---:|
| Dimensions | 97 | 314 |
| Unique vectors | 750 | 696 |
| Silhouette | -0.0510 | 0.0032 |
| Assigned members with negative silhouette | 79.3% | 56.4% |
| Seeded 80% subsample ARI | 0.3712 | 0.6624 |
| Nearby-parameter ARI | 0.1664 | 0.5836 |
| Noise | 36.8% | 33.1% |
| Largest cluster | 374 | 325 |
| Two-component PCA variance, display only | 9.1% | 21.9% |

The patient-fact pairwise distances are concentrated: the 25th and 75th percentiles are 1.3576
and 1.4817. This limits density contrast in 97 dimensions. The 97 features are also unevenly
distributed across blocks: 9 demographic, 24 condition, 24 medication, and 40 observation
features.

The screening profile gives 240 of 314 dimensions to individual criterion states, compared with
60 trial-rate, 12 criterion-family-rate, and 2 missing-category features. Many criteria test
related facts, so repeated criterion dimensions can outweigh the aggregate evidence structure.
The screening matrix is also imbalanced at the pair level: 12,531 of 15,000 results are
`likely_ineligible`, 1,522 are `needs_review`, and 947 are `potentially_eligible`.

These observations justify one feature-balancing experiment. They do not justify changing the
patients or choosing transformations after seeing repeated clustering outcomes.

## V2 representations

V2 creates two new versions:

- `r6.patient_fact.v2`;
- `r6.screening_profile.v2`.

V1 artifacts, metadata, DBSCAN reports, and FAISS indexes remain available as baseline evidence.

### Shared rules

1. Preserve the same 750-member order and its checksum.
2. Preserve explicit missingness and the separate `unknown` state.
3. Remove only zero-variance columns, recording every removed feature in metadata.
4. Fit preprocessing once on the complete fixed cohort and record all fitted statistics.
5. Scale each semantic feature block by `1 / sqrt(active block dimension)` so a large block does
   not dominate solely because it contains more columns.
6. L2-normalize the final dense `float32` vectors.
7. Record feature order, block membership, block weights, removed features, preprocessing version,
   and semantic checksums.

### Patient-fact V2

The source facts and feature meanings remain unchanged. V2 preprocessing will:

1. retain demographic, condition, medication, observation, evidence-age, and missingness fields;
2. leave binary indicators as explicit `0/1` values;
3. median-impute numeric values only after preserving their missingness indicators;
4. clip numeric values to the fitted 1st and 99th cohort percentiles;
5. robust-scale numeric values with the fitted median and interquartile range;
6. balance the demographic, condition, medication, and observation blocks using the shared rule;
7. globally L2-normalize the result.

If a numeric feature has no usable interquartile range, its recorded scale is `1.0`; missing values
are never converted to observed zeroes.

### Screening-profile V2

V2 retains every criterion's explicit `pass`, `fail`, and `unknown` state and its link to canonical
criterion evidence. It will:

1. retain criterion-state, trial-rate, criterion-family-rate, and missing-category blocks;
2. leave state indicators and bounded rates on their interpretable `0–1` scale;
3. down-weight exact repeated rule signatures inside the criterion-state block by
   `1 / sqrt(repetition count)`, using the canonical normalized rule JSON as the signature;
4. balance the four semantic blocks using the shared rule;
5. globally L2-normalize the result.

Repeated-rule weighting changes geometric influence only. It does not merge criterion evidence or
remove trial-version provenance.

## Frozen evaluation

V2 must use the same DBSCAN grid and stability protocol as V1:

- `eps`: 0.45, 0.60, 0.75, 0.90, 1.05, and 1.20;
- `min_samples`: 5, 10, 15, and 20;
- five seeded 80% subsample checks;
- four nearby-parameter checks;
- full-dimensional vectors for clustering;
- two-component seeded PCA for display only.

The V1 selection policy remains unchanged. V2 may not add grid values after inspecting its
results. Each representation is accepted or rejected independently.

An improved V2 DBSCAN representation must satisfy all of these predeclared criteria:

1. at least two clusters;
2. noise between 5% and 50%;
3. silhouette of at least 0.05;
4. subsample ARI of at least 0.50;
5. nearby-parameter ARI of at least 0.50;
6. largest cluster no larger than 75% of assigned members;
7. no leakage or loss of explicit missing/unknown states;
8. condition-composition review does not justify a phenotype claim.

Failure does not trigger another automatic transformation search. The V2 result will be reported,
and V1 remains the baseline negative or limited clustering finding.

## V2 exact similarity

Build a new exact CPU `IndexFlatIP` index for each V2 representation. Both must:

- contain exactly 750 vectors;
- exclude self-matches;
- agree with brute-force cosine neighbors for all 750 members;
- reject V1/V2 metadata or checksum mismatches;
- report top-10 neighbor overlap with V1 as a descriptive sensitivity measure, not an acceptance
  target.

Numerically tied float32 scores use the same declared verification tolerance and are ordered by
member identifier so FAISS and the brute-force reference remain deterministic at rank boundaries.

FAISS correctness is independent of DBSCAN acceptance. A V2 representation can fail the clustering
criteria while still producing a valid, versioned similarity index.

## Observed one-shot result

The authorized experiment completed once on 2026-08-16. All source-count, checksum, explicit-state,
finite-value, normalization, subject-order, and exact-index integrity checks passed.

| Representation | Clusters | Noise | Silhouette | Subsample ARI | Nearby ARI | Largest assigned cluster | Automated result |
|---|---:|---:|---:|---:|---:|---:|---|
| Patient fact V2 | 2 | 18.7% | 0.0466 | 0.7675 | 0.5216 | 604/610 (99.0%) | Fail |
| Screening profile V2 | 1 | 0.0% | Not defined | 1.0000 | 1.0000 | 750/750 (100%) | Fail |

Patient-fact V2 improved noise and stability relative to V1, but it did not meet the `0.05`
silhouette requirement and exceeded the 75% largest-cluster limit. Its second cluster contains only
six members; all six record type-2 diabetes and five record hypertension. That composition does
not support a claim that V2 discovered a new patient category.

Screening-profile V2 formed one density-connected cluster for every evaluated candidate that
formed a cluster. Its perfect ARI values are the stability of a trivial single-cluster partition,
not evidence of useful cohort structure.

The predeclared criteria were not relaxed after observing the near-threshold patient-fact
silhouette. Both V2 DBSCAN representations are rejected, V1 remains the immutable reportable
baseline, and no further automatic V2 transformation search is authorized.

## Exact-similarity result

Both V2 `IndexFlatIP` indexes passed all-member brute-force verification with zero mismatches.
Their top-10 neighbor overlap with V1 was:

| Representation | Members compared | Mean Jaccard | Minimum | Maximum |
|---|---:|---:|---:|---:|
| Patient fact V2 versus V1 | 750 | 0.2211 | 0.0000 | 0.6667 |
| Screening profile V2 versus V1 | 750 | 0.4920 | 0.0000 | 1.0000 |

The indexes are valid versioned sensitivity comparators, but exact computation does not establish
which representation retrieves more meaningful neighbors. Because V2 changes the patient-fact
neighbor set substantially and there is no independent relevance label, neither V2 index replaces
the active V1 index. The V2 indexes remain preserved for R8 sensitivity reporting.

## Final decision and stop point

V2 is complete and reviewed. The active V1 run and APIs remain unchanged. V2 transformation
experimentation stops here; the next implementation task remains the R5 risk backend, followed by
the coordinated R5/R6 frontend pass.

A separately accepted and implemented
[controlled cluster-recovery benchmark](r6-controlled-cluster-recovery-benchmark.md) asks whether
the unchanged analysis pipeline can recover predeclared latent structure in another generated
population. It does not reopen V2, retune this result, replace the accepted population, or change
activation. Its one full 750-member execution completed with intact seals, no structurally eligible
DBSCAN candidate, and below-threshold FAISS recovery; the result is recorded in the benchmark
report.

## Reproduction command

The completed experiment was produced from the repository root with:

```bash
backend/.venv/bin/python -m research.run_r6_v2_experiment \
  --run-directory artifacts/r6/r6-c21e487e-3b0d-5562-b7ad-3c7e7bbfdf2f
```

The command refuses to run against another source and now refuses to overwrite this reviewed V2
result.
