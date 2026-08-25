# R6 cohort runtime

R6 materializes a screening-derived cohort for population exploration and exact participant-neighbor
retrieval. It does not use R3 longitudinal data, dropout outcomes, risk predictions, SHAP values,
chat content, or RAG output.

The active cohort is the sealed V3.1 run `r6-v3-6091f06c-542d-5b00-8bdc-6fbd782c9510`: 750 unique
patient snapshots evaluated against 20 approved reference-trial versions, producing 15,000
deterministic screening pairs and 60,000 criterion results. Its patient-fact and screening-profile
matrices each contain one row per snapshot, so repeated trial evaluation does not increase a
patient's weight.

The [R6 V3 controlled cohort contract](r6-v3-controlled-cohort.md) is authoritative for the
generator, sealed configuration, private answer-key boundary, post-analysis evaluation, atomic
publication rule, and reviewed results. The active run passed its artifact seals, DBSCAN review,
exact-index verification, neighbor-relevance evaluation, and runtime-readability review.

For the complete experiment progression—V1/V2 diagnosis, controlled recovery, V3 population
geometry, all 750-member group counts, frozen configuration, selection protocol, and evaluated
results—read [R6 cohort methodology and experiment evolution](r6-cohort-methodology.md).

Earlier V1, V2, and controlled-recovery experiments remain retired provenance. They are not
runtime cohorts and cannot activate the API or frontend.

## Why the early DBSCAN silhouette scores were weak

The silhouette score checks whether an assigned member is closer to members of its own DBSCAN
group than to members of the nearest other group. It ranges from `-1` to `1`: values near `1`
indicate separated groups, values near `0` indicate overlap, and negative values mean a member
may be closer to another assigned group. It is reported only for non-noise members when that
calculation is meaningful.

The retired V1 cohort did not contain clear density-separated populations in its feature spaces.
It combined independently sampled conditions, medications, observations, and broadly varying
fact dates. The resulting patient-fact vectors formed an overlapping continuum rather than
compact, internally coherent groups; independent fact timing also added variation unrelated to
the clinical profile. Its patient-fact silhouette was approximately `-0.05`. In the
screening-profile space, widespread similar ineligibility patterns across the fixed reference
panel further reduced contrast, producing a silhouette close to `0`.

V2 changed feature weighting but did not change that underlying population geometry. It produced
trivial one- or two-group collapse rather than evidence of useful density modes. The controlled
recovery experiment then held the pipeline constant and showed that small planted shifts were
still too weak relative to within-group variation and high-dimensional dilution. These results
identified the cohort design—not the DBSCAN or FAISS implementation—as the limiting factor.

V3 therefore kept the feature builders, trial panel, bounded DBSCAN protocol, and exact FAISS
indexer fixed, while using correlated patient profiles with coherent age, condition, medication,
observation, and encounter-timing patterns. It also retains an intentionally broad background
group that DBSCAN can leave as noise instead of forcing into a cluster. This controlled
positive-control design produced patient-fact silhouette `0.4042` and screening-profile
silhouette `0.8923`. Those values show that the pipeline can recover separated structure when
the input population genuinely contains it; they are not a claim about real-world disease
phenotypes.

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
TRIALSYNC_RESEARCH_COHORT_ACTIVE_RUN=r6-v3-6091f06c-542d-5b00-8bdc-6fbd782c9510
```

Regenerate and verify from the repository root with:

```bash
backend/.venv/bin/python -m pip install --editable './backend[dev,research,research-r6]'
backend/.venv/bin/python -m research.run_r6_v3_pipeline --output-root artifacts/r6
backend/.venv/bin/pytest backend/tests/research -q
```

Generated artifacts remain under `artifacts/r6/` and are excluded from Git. The repository stores
the contracts, builders, tests, and aggregate evidence in this report.

## Frontend delivery

The sealed reference artifacts, saved-screening projection adapter, and artifact-backed APIs are
implemented. Saved screening details now independently request patient-fact or screening-profile
DBSCAN context and exact external-vector FAISS neighbors, including PCA overlay coordinates,
unassigned handling, cosine scores, and transparent feature differences. The dedicated population
Cohort Atlas supports both representations, cluster/noise filtering, member detail, and exact
neighbor inspection. Saved-screening results deep-link into the Atlas as an out-of-sample overlay;
the Atlas is not the sole entry point for either action. Neither action depends on dropout
prediction or changes eligibility.
