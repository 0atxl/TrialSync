# R5 dropout-risk backend

> Integration revision: the model-package, inference, explanation, platform enrollment, complete
> longitudinal event, immutable follow-up snapshot, and prediction foundations described here are
> implemented. Runtime participants use the saved-screening-owned path defined in
> [`research-integration-contract.md`](research-integration-contract.md). The 4,000-row R3 data is
> model-training lineage only.

R5 exposes the active XGBoost candidate `xgboost-06` as model
`dropout-xgboost-06-v1` through an authenticated, versioned research API. This integration does
not retrain the supplied model or alter deterministic eligibility. Its reported performance is
limited to the controlled synthetic task and is not clinical or real-world validation.

## Runtime model package

The runtime package contract is `r5-risk-model-package-v1`. Packaging copies the reviewed local
XGBoost pipeline, verifies its approved SHA-256 checksum, copies the frozen feature schema, and
writes a manifest containing the model, dataset, schema, threshold, horizon, band-policy, and test
metric metadata. Packaging performs a fixed-input inference check and does not fit or update the
model.

Install the CPU-only inference dependencies and create the package from the repository root:

```bash
backend/.venv/bin/python -m pip install -e './backend[research-risk]'
backend/.venv/bin/python -m research.package_r5_model --output-root artifacts/r5
```

The reviewed source pipeline must be available at
`artifacts/r4/imported/xgboost_06/models/xgboost_pipeline.joblib`. Binary model packages remain
ignored local artifacts. Configure the accepted package with:

```text
TRIALSYNC_RESEARCH_RISK_ACTIVE_MODEL=dropout-xgboost-06-v1
```

The service loads the package lazily. It verifies the artifact and feature-schema checksums and
compares the manifest with the immutable database model record before inference. A missing or
inconsistent package degrades only the optional research capability; it does not make the core
screening API unavailable.

## Feature contract

The model uses the exact 27-feature `r4-day30-features-v2` day-30 schema:

- 12 baseline fields: condition category, site region, treatment arm, age, sex, baseline
  functional severity, reported burden, comorbidity burden, treatment burden, travel/access
  burden, support availability, and medication count;
- 15 day-30 follow-up fields: latest functional severity, severity slope, observation count,
  scheduled- and missed-dose counts, missed-dose rate, longest missed-dose streak,
  delayed- and missed-visit counts, missed-visit rate, longest missed-visit streak, mean visit
  delay, measurement missingness, adverse-event count, and adverse-event burden.

Every value has an explicit source. The saved screening supplies only baseline values it owns,
such as age from the immutable date of birth and condition category from the approved trial
version. The active integration requests one explicit aggregate through-day-30 summary, including
the two longest-streak values, and derives rates and slopes on the server. Streaks are not guessed
from totals. Missing, non-finite, out-of-range, or unknown fields prevent snapshot creation;
missing values are never converted to zero. Unsupported trial conditions return
`unsupported_model_input` and leave deterministic eligibility unchanged.

## Immutable linkage and persistence

The foundation migration `20260820_0013` adds:

- `research_model_versions`, containing the approved runtime metadata;
- `research_enrollments`, joining an owner-scoped saved screening to its immutable patient snapshot
  and approved trial version;
- `research_dose_events`, `research_visit_events`, `research_measurements`, and
  `research_adverse_events`, with append-only correction lineage;
- `research_follow_up_snapshots`, containing derived, source-preserved day-30 features and explicit
  missing fields;
- `research_predictions`, storing the exact follow-up snapshot hash, probability, risk band, model
  metadata, and top contributions.

Migration `20260827_0014` adds `input_summary_json` to immutable follow-up snapshots. The earlier
event tables remain for migration compatibility, but they are no longer exposed by the active R5
API or used by the prediction-entry workflow.

Migration `20260828_0015` adds append-only enrollment baseline revisions and links new follow-up
snapshots to the revision used to build them. POST creates an enrollment once; PUT appends an
idempotent correction and materializes a new follow-up snapshot when prior day-30 inputs exist.
Corrections never rewrite an existing snapshot or prediction. The migration changes no historical
feature values, hashes, prediction outputs, explanations, or timestamps. It labels v2 only when a
payload satisfies the frozen 27-feature contract and repairs legacy link mismatches by inserting
exact snapshots from the immutable feature copies already stored on predictions. The historical
XGBoost-05/v1 model row remains immutable; XGBoost-06/v2 has a separate model-version ID. Migration
`20260828_0016` applies the same provenance split forward to local databases that had already run
the earlier development form of `0015`.

A screening may have only one immutable enrollment episode. No runtime row resolves into the R3
training dataset. Predictions remain idempotent for the same owner, enrollment, model, and
feature-snapshot hash. No risk field is added to `patients`, `screenings`, or deterministic
criterion evaluations.

## API

All routes require authentication and enforce record ownership:

```text
GET  /api/v1/research/risk/models
GET  /api/v1/research/risk/models/{model_version}
GET  /api/v1/research/screenings/{screening_id}/capabilities
POST /api/v1/research/screenings/{screening_id}/enrollment
PUT  /api/v1/research/screenings/{screening_id}/enrollment
GET  /api/v1/research/enrollments/{enrollment_id}
POST /api/v1/research/enrollments/{enrollment_id}/day30-summary
GET  /api/v1/research/enrollments/{enrollment_id}/follow-up-snapshots
GET  /api/v1/research/risk/screenings/{screening_id}/context
GET  /api/v1/research/risk/worklist
POST /api/v1/research/risk/predictions
POST /api/v1/research/risk/scenarios
GET  /api/v1/research/risk/predictions
GET  /api/v1/research/risk/predictions/{prediction_id}
GET  /api/v1/research/trial-overview
GET  /api/v1/research/trial-overview/{trial_version_id}
```

The context endpoint reports `unlinked`, `incomplete`, `ready`, or
`unsupported_model_input`. Submitting changed aggregate
inputs creates or reuses the corresponding immutable snapshot and estimate. The owner-scoped
worklist returns one row per potentially eligible screening with patient/trial labels, workflow
state, latest current estimate or `null`, update time, and next action. Follow-up snapshots return
every required feature with its group, value, source, and missing state. A prediction response includes the
day-90 dropout probability, stored threshold, versioned risk band, model identity, source-preserved
feature snapshot, and the eight largest native XGBoost Tree SHAP contributions. Contributions
describe model behavior; they are not causal explanations.

Trial overviews group ordinary saved-screening states by approved trial-version ID. Retention-risk
counts include only potentially eligible screenings with a version-matched enrollment link and
prediction from the active model. Eligible, linked, and unlinked denominators are returned
explicitly.

## Interpretation and remaining work

The output is a day-30-to-day-90 research prediction for the generated R3 task. It is not a day-0
prediction, clinical probability, eligibility score, or retention recommendation. The threshold
is `0.445`; the versioned display bands are lower, near threshold, and higher. The
response always states: `Research prediction only; not a clinical or eligibility decision.`

The R5 backend integration passes focused persistence, API, feature, and model-package tests. The
saved-screening frontend launches a focused route for baseline setup, one compact aggregate day-30
form, and the dropout estimate. It asks directly for expected/missed doses, their longest missed
run, visit totals and their longest missed run,
assessment totals/latest severity, and adverse-event count/burden; missing values remain missing.
The saved eligibility result is unchanged. Probability, threshold,
horizon, and human-readable factors are primary;
model/provenance values and numeric SHAP contributions are under Technical details. The Dropout
dashboard lists every potentially eligible screening across not-started, information-needed,
ready-to-predict, and estimate-available states.

The scenario endpoint performs non-persisting inference for the current aggregate and exactly one
or two additional consecutive missed-dose opportunities, updating counts, rate, and streak while
holding every other feature fixed. XGBoost is piecewise constant, so adjacent scenario points may
legitimately have the same probability.
