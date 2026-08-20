# R5 dropout-risk backend

> Integration revision: the model-package, inference, explanation, platform enrollment, complete
> longitudinal event, immutable follow-up snapshot, and prediction foundations described here are
> implemented. Runtime participants use the saved-screening-owned path defined in
> [`research-integration-contract.md`](research-integration-contract.md). The 4,000-row R3 data is
> model-training lineage only.

R5 exposes the user-selected XGBoost candidate `xgboost-05` through an authenticated,
versioned research API. It does not retrain R4, change the frozen comparison result, or alter
deterministic eligibility. The original R4 validation rule selected LightGBM; XGBoost remains the
separately documented runtime choice made after review of the frozen comparison.

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
`artifacts/r4/imported/r4_manual/models/xgboost_pipeline.joblib`. Binary model packages remain
ignored local artifacts. Configure the accepted package with:

```text
TRIALSYNC_RESEARCH_RISK_ACTIVE_MODEL=dropout-xgboost-05-v1
```

The service loads the package lazily. It verifies the artifact and feature-schema checksums and
compares the manifest with the immutable database model record before inference. A missing or
inconsistent package degrades only the optional research capability; it does not make the core
screening API unavailable.

## Feature contract

The model uses the exact 22-feature R3 day-30 schema:

- 12 baseline fields: condition category, site region, treatment arm, age, sex, baseline
  functional severity, reported burden, comorbidity burden, treatment burden, travel/access
  burden, support availability, and medication count;
- 10 day-30 follow-up fields: latest functional severity, severity slope, observation count,
  missed-dose rate, delayed-visit count, missed-visit rate, mean visit delay, measurement
  missingness, adverse-event count, and adverse-event burden.

Every value has an explicit source. The saved screening supplies only baseline values it owns,
such as age from the immutable date of birth and condition category from the approved trial
version. The accepted integration derives remaining values from the platform research enrollment
and its dose, visit, measurement, and adverse-event records. Missing, non-finite, out-of-range, or
unknown fields prevent a ready follow-up snapshot; missing values are never converted to zero.

## Immutable linkage and persistence

The current foundation migration `20260820_0013` adds:

- `research_model_versions`, containing the approved runtime metadata;
- `research_enrollments`, joining an owner-scoped saved screening to its immutable patient snapshot
  and approved trial version;
- `research_dose_events`, `research_visit_events`, `research_measurements`, and
  `research_adverse_events`, with append-only correction lineage;
- `research_follow_up_snapshots`, containing derived, source-preserved day-30 features and explicit
  missing fields;
- `research_predictions`, storing the exact follow-up snapshot hash, probability, risk band, model
  metadata, and top contributions.

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
GET  /api/v1/research/enrollments/{enrollment_id}
GET  /api/v1/research/enrollments/{enrollment_id}/events
POST /api/v1/research/enrollments/{enrollment_id}/dose-events
POST /api/v1/research/enrollments/{enrollment_id}/visit-events
POST /api/v1/research/enrollments/{enrollment_id}/measurements
POST /api/v1/research/enrollments/{enrollment_id}/adverse-events
POST /api/v1/research/enrollments/{enrollment_id}/follow-up-snapshots
GET  /api/v1/research/enrollments/{enrollment_id}/follow-up-snapshots
GET  /api/v1/research/risk/screenings/{screening_id}/context
POST /api/v1/research/risk/predictions
GET  /api/v1/research/risk/predictions
GET  /api/v1/research/risk/predictions/{prediction_id}
GET  /api/v1/research/trial-overview
GET  /api/v1/research/trial-overview/{trial_version_id}
```

The context endpoint reports `unlinked`, `incomplete`, or `ready`. Follow-up snapshots return every
required feature with its group, value, source, and missing state. A prediction response includes the
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
is `0.21347740292549133`; the versioned display bands are lower, near threshold, and higher. The
response always states: `Research prediction only; not a clinical or eligibility decision.`

The R5 backend integration passes focused persistence, API, feature, and model-package tests. The
remaining R5 work is the saved-screening frontend for enrollment setup, event capture, follow-up
readiness, prediction, probability/threshold/horizon/model metadata, and SHAP contributions.
