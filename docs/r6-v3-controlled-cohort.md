# R6 V3 controlled cohort contract

R6 V3 is a separately versioned, controlled correlated-group cohort used to verify that the
unchanged TrialSync representation, DBSCAN, and exact-similarity pipeline can recover deliberately
present structure. It does not replace the immutable V1 baseline, rewrite the rejected V2 result,
or change the completed controlled-recovery benchmark.

The permitted claim is narrow: the R6 pipeline can recover stable, interpretable structure when
that structure exists in its versioned input space. V3 does not establish clinical phenotypes,
diagnoses, treatment groups, or eligibility recommendations.

## Frozen generation boundary

| Field | Value |
|---|---|
| Cohort contract | `r6-cohort-v3` |
| Generator | `r6-controlled-groups-v3.1` |
| Seed | `60818` |
| Screening date | `2026-08-16` |
| Patient snapshots | 750 |
| Approved trial versions | 20 |
| Screening pairs | 15,000 |
| Expected criterion results | 60,000 |
| Structured groups | four groups of 160 members |
| Background members | 110 |
| Output root | `artifacts/r6` |

The `v3.1` generator identifier distinguishes the repository contract from earlier development
iterations that used the same seed while the generator source was still changing. The complete
configuration—not merely the seed—is serialized and checksummed.

The four structured groups use correlated condition, medication, observation, age, and encounter
patterns. The background group uses broader variation and more incomplete evidence. These
differences are deliberate controls. In particular, missingness can help distinguish background
members because missing-state indicators are valid representation features; it must therefore be
reported as part of the population design rather than described as independently discovered
structure.

## Unchanged analysis boundary

V3 holds the following R6 components constant:

- the frozen 20-version reference panel and criterion order;
- the deterministic single-screening engine;
- `r6.patient_fact.v1`, 97 dimensions;
- `r6.screening_profile.v1`, 314 dimensions;
- median imputation, standardization, and L2 normalization;
- the bounded V1 DBSCAN grid;
- seeded subsample and nearby-parameter stability checks;
- exact CPU `IndexFlatIP` indexes and all-member brute-force verification.

At a top-k boundary, FAISS and NumPy may return different member identifiers whose float32 cosine
scores are equal within the declared tolerance. Such a substitution is accepted only if every
strictly higher-scoring member is retained and every returned score matches its brute-force score.

The generation answer key cannot be imported by feature construction, DBSCAN selection, index
construction, the read-only runtime service, or API serialization. Dropout outcomes, predictions,
SHAP values, chat content, and retrieval output remain excluded.

## Artifact and seal layout

```text
artifacts/r6/<run_id>/
  manifest.json
  generation_config.json
  patients.parquet
  patient_facts.parquet
  reference_panel.json
  screening_pairs.parquet
  criterion_results.parquet
  members.json
  representations/
  clusters/
  projections/
  indexes/
  private/
    answer_key.json
    manifest.json
  evaluation/
    report.json
    manifest.json
```

The public manifest records the complete generation-config semantic checksum, implementation-file
checksums, and the checksum of the private manifest. The private manifest seals the answer key,
group counts, cohort checksum, and generation-config checksum. The evaluator refuses altered,
missing, cross-run, or incomplete inputs.

An existing run directory is immutable. The complete pipeline builds in a temporary sibling
directory, performs analysis and evaluation there, and publishes the run with one final rename.
It refuses to overwrite a run identifier that already exists.

## Evaluation contract

The post-analysis evaluator reports, for both representations:

- selected DBSCAN parameters, cluster count, noise, and silhouette;
- subsample and nearby-parameter adjusted-rand stability;
- assigned-member count and assignment coverage;
- weighted and macro cluster purity among assigned members;
- all-member adjusted-rand agreement with the private grouping;
- per-group assignment and majority-aligned recall;
- background-to-noise recall;
- exact-index verification;
- top-10 same-group precision, macro precision, top-one rate, and lift.

Purity and coverage must be reported together. A result with pure cluster cores but many noise
members is not complete population recovery. Screening-profile clusters are eligibility-evidence
profiles over the reference panel, not disease categories.

The evaluator returns `verified_for_review`; it does not silently activate the run. Runtime
activation occurs only after the generated report and API behavior have been reviewed.

## Reviewed repository result

Run `r6-v3-a91d87c1-d360-565d-b7d9-c12d120e3e8d` produced four patient-fact cluster cores with
silhouette `0.4042`, subsample stability `0.9990`, nearby-parameter stability `0.9805`, and 100%
weighted purity among 465 assigned members. Assignment coverage was 62.0%, with 285 members
treated as noise. All 110 background members were noise in patient-fact space.

The screening-profile space produced 11 eligibility-evidence profiles with silhouette `0.8923`,
subsample stability `0.9889`, nearby-parameter stability `0.9815`, 99.2% weighted purity, and
67.7% assignment coverage. Background-noise recall was 96.4%.

Both exact indexes passed all-member brute-force verification. Structured-group top-10 neighbor
precision was 92.2% in patient-fact space and 92.0% in screening-profile space, corresponding to
more than 4.3 times the size-weighted baseline. The on-disk public/private seals, evaluation-report
checksum, and runtime artifact loading all passed review on 2026-08-20. This run is approved as the
R6 runtime cohort; its groups remain controlled analysis structures rather than diagnoses.

## Execution

Install the existing R6 dependency set, then run from the repository root:

```bash
backend/.venv/bin/python -m research.run_r6_v3_pipeline \
  --output-root artifacts/r6
```

The command prints the run identifier, public manifest, evaluation report, and the matching
`TRIALSYNC_RESEARCH_COHORT_ACTIVE_RUN` setting. The reviewed setting is:

```bash
export TRIALSYNC_RESEARCH_COHORT_ACTIVE_RUN=r6-v3-a91d87c1-d360-565d-b7d9-c12d120e3e8d
```

Generated artifacts remain excluded from Git.
