# R6 cohort history and active V3 runtime

R6 materializes a separate screening-derived cohort for population exploration and exact
participant-neighbor retrieval. It does not use the R3 longitudinal enrollment data, dropout
outcomes, risk predictions, SHAP values, chat content, or RAG output.

## Historical V1 baseline

| Field | Value |
|---|---|
| Run ID | `r6-c21e487e-3b0d-5562-b7ad-3c7e7bbfdf2f` |
| Contract | `r6-cohort-v1` / `parquet-v1` |
| Seed and screening date | `60816` / `2026-08-16` |
| Patient snapshots | 750 |
| Approved reference trial versions | 20 |
| Deterministic screening pairs | 15,000 |
| Criterion results | 60,000 |
| Patient facts | 12,606 |
| Patient-fact representation | `r6.patient_fact.v1`, 97 dimensions |
| Screening-profile representation | `r6.screening_profile.v1`, 314 dimensions |

The 15,000 pair evaluations are intermediate evidence records. Both analysis matrices contain
exactly 750 rows, one per immutable patient snapshot. Repeating a patient across the trial panel
does not increase that patient's weight in clustering or similarity.

The run manifest records file hashes and semantic checksums for the cohort, snapshots, facts,
reference panel, criterion order, screening pairs, and criterion results. A second run with the
same seed reproduced the semantic checksums and all source-table, representation, projection, and
FAISS index hashes. Build timestamps changed as expected.

## DBSCAN evaluation

DBSCAN was evaluated separately in each full-dimensional, normalized representation over the
bounded grid:

- `eps`: 0.45, 0.60, 0.75, 0.90, 1.05, and 1.20;
- `min_samples`: 5, 10, 15, and 20;
- five seeded 80% subsample checks per candidate;
- four nearby-parameter checks per candidate.

Selection excludes all-noise and single-cluster outcomes from outranking a genuine partition only
because those trivial outcomes receive perfect adjusted-rand stability. When available, selection
first considers multi-cluster candidates with no more than 50% noise, then ranks bootstrap
stability, nearby-parameter stability, silhouette, and noise fraction. Every candidate remains in
the report; selection does not hide unfavorable alternatives.

| Representation | Selected parameters | Clusters | Noise | Silhouette | Subsample ARI | Nearby-parameter ARI |
|---|---:|---:|---:|---:|---:|---:|
| Patient fact | `eps=1.05`, `min_samples=5` | 16 | 36.8% | -0.0510 | 0.3712 | 0.1664 |
| Screening profile | `eps=0.75`, `min_samples=5` | 12 | 33.1% | 0.0032 | 0.6624 | 0.5836 |

These are exploratory partitions, not validated phenotypes. Patient-fact separation is weak: its
negative silhouette and low stability show overlapping groups, one cluster contains 374 members,
and several clusters contain fewer than ten. Condition-composition inspection also found strong
condition enrichment in some small clusters, including type-1-diabetes lift in small groups and
type-2-diabetes enrichment in another small group. This means the patient-fact result partly
reflects recorded condition categories and should not be presented as a newly discovered disease
taxonomy.

The screening-profile partition is more stable but still has a near-zero silhouette. Its groups
are therefore described only as evidence profiles across the frozen trial panel. Neither cluster
space changes, supports, or overrides an eligibility result.

### What weak separation means

The V1 implementation is reproducible, but most assigned members do not sit inside cleanly
separated groups. Among assigned members, 79.3% in patient-fact space and 56.4% in
screening-profile space have negative individual silhouette values. The patient-fact result is
also highly sensitive to subsampling and small parameter changes.

This behavior is consistent with the observed geometry rather than an execution failure:

- patient-fact distances are concentrated in the 97-dimensional space;
- feature blocks have unequal numbers of dimensions;
- 240 of 314 screening-profile dimensions are individual criterion states;
- related rules recur across the reference panel;
- screening outcomes are dominated by the broad `likely_ineligible` state;
- one large density-connected group coexists with small groups and noise in both spaces.

The V1 run is therefore retained as an immutable baseline, not promoted as evidence of strong
natural patient categories.

## Retired V2 comparison

A single bounded V2 representation experiment reused the exact accepted cohort,
reference panel, screening pairs, criterion results, member order, and semantic checksums. It may
change only transparent preprocessing and feature-block weighting. It may not regenerate records,
plant cluster labels, add outcome-derived fields, or expand the DBSCAN grid after viewing results.

Patient-fact V2 improved stability but collapsed 604 of 610 assigned members into one cluster and
missed the silhouette threshold. Screening-profile V2 collapsed all 750 members into one cluster.
Both V2 DBSCAN representations were rejected without relaxing the predeclared criteria. Both exact
V2 indexes passed brute-force verification. The experiment implementation and local sensitivity
artifacts were retired after review; neither representation is active.

## Retired controlled-recovery benchmark

The V1 and V2 results show that the accepted population does not contain robust density-separated
groups under the evaluated representations and protocols. They do not prove whether the pipeline
can recover groups when a separate population contains predeclared latent structure.

The one frozen 750-member positive-control run
`r6-recovery-9023c03a-30d8-5665-9016-ef8b537e29d0` reused the trial panel and screening engine,
kept its answer key sealed until after label-free DBSCAN and FAISS analysis, and completed with
intact seals. It produced no qualifying DBSCAN structural candidate and below-threshold
patient-fact V2 FAISS recovery. It never activated a runtime cohort or added an API/frontend
surface; its implementation and local artifacts were retired after review.

## Active V3 controlled cohort

The completed recovery benchmark showed that its deliberately overlapping population did not
retain enough separable structure under the approved representations. The user subsequently
authorized a new, separately versioned controlled cohort with correlated groups and cohesive
encounter timing while keeping the reference panel, feature builders, DBSCAN grid, and FAISS
implementation unchanged.

The [R6 V3 controlled cohort contract](r6-v3-controlled-cohort.md) records the final `v3.1`
generator, complete configuration seal, private answer-key boundary, post-analysis evaluator,
atomic publication rule, and correct purity/coverage interpretation. The authoritative repository
run `r6-v3-a91d87c1-d360-565d-b7d9-c12d120e3e8d` completed, passed seal and runtime-readability
review, and is the only approved R6 runtime cohort.

## Exact FAISS indexes

R6 builds two CPU `IndexFlatIP` indexes over L2-normalized `float32` vectors. Inner product on unit
vectors is cosine similarity. The observed norm range in both representations was
`0.99999988–1.00000012`.

Verification queried every one of the 750 members in each index and compared its neighbors and
scores with brute-force cosine search:

| Representation | Vectors | Dimensions | Members checked | Mismatches |
|---|---:|---:|---:|---:|
| Patient fact | 750 | 97 | 750 | 0 |
| Screening profile | 750 | 314 | 750 | 0 |

Queries exclude the selected member from its own results and return transparent raw-feature
differences. A nearest neighbor means only "closest under this frozen representation"; it is not
eligibility evidence, a cluster assignment, or a recommendation.

FAISS and the NumPy brute-force reference can accumulate float32 dot products a few ULPs apart.
Scores within the verification tolerance (`rtol=1e-5`, `atol=1e-6`) are treated as one numerical
tie group. Verification accepts an identifier substitution at the requested-neighbor boundary only
when the scores are equivalent within that tolerance; it still requires matching scores, every
strictly higher-scoring member, unique results, and self-exclusion.

## Runtime contract

The artifact-backed backend is read-only and degrades independently if the active run, a required
file, checksum, vector norm, index, or version mapping is invalid. Core screening readiness is not
coupled to R6 availability.

Authenticated routes are:

```text
GET  /api/v1/research/cohorts/runs
GET  /api/v1/research/cohorts/runs/{run_id}
GET  /api/v1/research/cohorts/runs/{run_id}/clusters
GET  /api/v1/research/cohorts/runs/{run_id}/members
GET  /api/v1/research/cohorts/runs/{run_id}/members/{member_id}
POST /api/v1/research/similarity/queries
```

The local accepted run is selected with:

```dotenv
TRIALSYNC_RESEARCH_COHORT_ACTIVE_RUN=r6-v3-a91d87c1-d360-565d-b7d9-c12d120e3e8d
```

Regenerate and verify from the repository root with:

```bash
backend/.venv/bin/python -m pip install --editable './backend[dev,research,research-r6]'
backend/.venv/bin/python -m research.run_r6_v3_pipeline --output-root artifacts/r6
backend/.venv/bin/pytest backend/tests/research -q
```

Generated artifacts remain under `artifacts/r6/` and are excluded from Git. The repository stores
the contracts, builders, tests, and aggregate evidence in this report.

## Remaining R6 delivery

The R6 data/backend foundation, V1 baseline, bounded V2 comparison, and one-run controlled-recovery
benchmark are complete. The V3 controlled-cohort generator, seals, evaluator, and atomic runner are
implemented, and its full repository run is reviewed and approved. Cohort Atlas frontend work
remains deferred to the coordinated R5/R6 integration pass after the R5 risk backend is implemented.
