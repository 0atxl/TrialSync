# TrialSync Research Extension: Phased Implementation Plan

**Date:** 2026-07-24
**Status:** R0 approved and locked on 2026-07-26; R1 is the next authorized phase
**Relationship to the current application:** Incremental extension after the completed deterministic TrialSync workflow. This plan does not replace the existing architecture or reopen completed rebuild phases.

## 1. Purpose

This document is the authoritative implementation sequence for the selected TrialSync research
extension. It converts the original bootcamp brief into bounded, testable phases while
preserving the completed deterministic screening product.

The approved extension contains:

1. Canonical evidence-backed PDF reporting and GitHub Actions CI.
2. A separate synthetic longitudinal enrollment dataset for dropout-risk research.
3. Logistic regression, XGBoost, LightGBM, MLflow, SHAP, and a missed-dose Scenario Lab.
4. A screening-derived patient cohort for DBSCAN clustering, FAISS similarity, and the
   Cohort Atlas.
5. ClinicalTrials.gov discovery with measured retrieval, bounded grounded generation,
   citation validation, and Groq 429 resilience.
6. Integrated evaluation, documentation, and presentation evidence.

The feasibility evidence and rationale are recorded in
[`research-pivot-findings.md`](research-pivot-findings.md) and
[`research-feasibility-rating-and-local-llm.md`](research-feasibility-rating-and-local-llm.md).

The extension has two distinct surfaces:

```text
TrialSync core product
  -> reviewed patient/trial inputs
  -> deterministic pass/fail/unknown screening
  -> canonical evidence and downloadable report

TrialSync research analytics
  -> longitudinal synthetic enrollment dataset
  -> dropout-risk experiments and Scenario Lab
  -> screening-derived patient cohort
  -> DBSCAN clustering, FAISS similarity, and Cohort Atlas
  -> public-trial retrieval and grounded RAG
  -> clearly separated research outputs
```

The deterministic screening result remains the source of truth. Research predictions, clusters, similarity results, SHAP values, retrieval scores, and LLM prose must never change eligibility.

## 2. Current baseline

The following capabilities already exist and should not be rebuilt:

- FastAPI, PostgreSQL, SQLAlchemy, Alembic, React, TypeScript, and Vite foundation.
- User-owned synthetic patients, facts, trials, versions, and criteria.
- Immutable patient snapshots and approved trial versions.
- Pure deterministic screening with conservative `pass`, `fail`, and `unknown`.
- Transactional single and bounded batch screening history.
- Evidence-first screening detail and batch-matrix interfaces.
- Review-first pasted-text and PDF import.
- Local Tesseract OCR with bounded failure handling.
- Provider-neutral Groq candidate extraction with exact-source validation.
- Screening-scoped grounded explanation chat with bounded persisted memory.
- Synthetic demo seeds, held-out fixture evaluation, browser workflows, and dependency audits.
- Backend and frontend Dockerfiles plus development and production Compose configurations.

Known extension gaps:

- No downloadable canonical screening-result PDF.
- No GitHub Actions workflow.
- No synthetic longitudinal enrollment dataset for dropout research.
- No screening-derived patient cohort/reference-trial matrix.
- No dropout-risk model, model registry, calibration report, or SHAP explanation.
- No research-risk inference API or UI.
- No patient-fact or screening-profile clustering/similarity experiment.
- No FAISS index.
- No ClinicalTrials.gov discovery adapter or retrieval evaluation.
- No research-extension evaluation/reporting package.

## 3. Fixed decisions

These decisions apply to every phase unless the user explicitly changes them after reviewing this document.

### 3.1 Data boundary

- The repository, automated tests, demo, Groq requests, screenshots, and downloadable reports use fictional synthetic participant data only.
- The longitudinal dropout dataset is generated specifically for this project with fixed
  seeds and documented causal assumptions.
- The cohort dataset is generated from unique synthetic patient snapshots evaluated against
  a fixed, versioned panel of approved synthetic trial versions.
- MIMIC-III, PRO-ACT, n2c2, NCT02054715-D1, and Project Data Sphere are not implementation dependencies.
- Restricted datasets may be discussed as future validation sources but are never required to run the project.
- ClinicalTrials.gov may be accessed because it contains public study records, not patient records.

### 3.2 Decision boundary

- Eligibility remains deterministic.
- A dropout probability is not an eligibility score.
- A cluster is not a diagnosis or trial recommendation.
- Similar patients are not screening evidence.
- A retrieval score is not proof of eligibility.
- SHAP explains a model output; it does not establish causality.
- LLM text supplements canonical stored results; it does not create the canonical result.

### 3.3 Product boundary

- Research analytics live in a visibly labelled research area.
- Existing screening contracts remain backward compatible unless a phase explicitly documents a versioned addition.
- The core application continues to work when research dependencies, MLflow, FAISS, ClinicalTrials.gov, or Groq are unavailable.
- No queue, Redis, Celery, microservice, Kubernetes, vector database, billing system, or EHR integration is introduced.
- Ollama and local language models are not part of TrialSync's default provider path.
- Groq remains optional; deterministic extraction, ranked retrieval, canonical explanations,
  and screening continue to work during provider cooldown or failure.

### 3.4 Claim boundary

Allowed claims:

- "Synthetic dropout-risk modeling demonstration."
- "Research-only cohort discovery over generated patient profiles."
- "Similarity in a versioned synthetic feature space."
- "Public trial discovery using ClinicalTrials.gov records."
- "Evidence-backed deterministic pre-screening."

Disallowed claims:

- "Predicts whether real clinical-trial participants will drop out."
- "Clinically validated dropout model."
- "Discovers real disease phenotypes."
- "Automatically determines trial eligibility."
- "Production clinical platform."
- "HIPAA compliant" or "hospital ready."
- "Continuous deployment" unless a real tested deployment target is configured.

### 3.5 Selected scope

Approved for inclusion:

- Canonical evidence-backed screening PDF reports.
- GitHub Actions continuous integration and reproducible delivery checks.
- A versioned synthetic longitudinal participant dataset.
- Logistic-regression, XGBoost, and LightGBM dropout-risk experiments with MLflow and SHAP.
- A separate research-risk API and UI.
- DBSCAN cohort discovery and FAISS participant similarity.
- ClinicalTrials.gov discovery plus a measured, genuinely retrieval-augmented bounded generator.
- Integrated evaluation, documentation, and presentation evidence.

Deferred:

- BioBERT clinical extraction or patient–criterion matching.
- Restricted patient-level datasets as runtime, build, test, or public-demo dependencies.
- Automatic continuous deployment.
- Local small-model fallback for Groq failures.

## 4. Proposed final architecture

```text
backend/src/trialsync/
  reports/                    # canonical screening report assembly/rendering
  research/
    dropout_data/            # longitudinal enrollment generation and validation
    dropout_features/        # leakage-safe fixed-horizon features
    risk/                    # training, evaluation, registry, inference
    cohort_profiles/         # patient facts and screening-profile matrices
    cohorts/                 # DBSCAN, stability, projections, summaries
    similarity/              # FAISS index build/query and metadata
    trial_discovery/         # ClinicalTrials.gov adapter, retrieval, and bounded RAG
    provider_resilience/     # Groq cooldown, cache, concurrency, and fallbacks

backend/research/
  configs/                    # versioned experiment configurations
  reports/                    # checked-in aggregate evaluation reports
  schemas/                    # dataset/feature/model contracts

artifacts/                    # ignored local generated models and indexes
mlruns/                       # ignored local MLflow store
```

Runtime product data stays in PostgreSQL. Generated training files, model binaries, FAISS indexes, MLflow runs, and temporary report files do not belong in Git. Only schemas, generator code, small synthetic fixtures, aggregate metrics, plots approved for publication, and reproducibility metadata are committed.

## 5. Phase dependency map

```text
R0 Scope lock
 |
 +--> R1 Canonical screening report
 |
 +--> R2 Continuous integration
 |
 +--> R3 Synthetic longitudinal dropout protocol and dataset
       -> R4 Dropout model experiments
             -> R5 Versioned risk API and Scenario Lab
 |
 +--> R6 Screening-derived cohorts, DBSCAN, FAISS, and Cohort Atlas
 |
 +--> R7 ClinicalTrials.gov discovery and genuine RAG
 |
 +--> R8 Integrated evaluation, documentation, and presentation
```

R1 and R2 may proceed independently after R0. R4 depends on the accepted R3 longitudinal
dropout dataset, and R5 depends on an R4 model passing its declared acceptance criteria. R6
uses a different screening-derived patient cohort and does not depend on the dropout dataset.
R7 is independent of both research datasets and includes the Groq resilience work required by
grounded generation.

## 6. Phase R0 — Scope lock and research protocol

### Objective

Record the approved extension boundaries and prevent later phases from silently expanding them.

### Locked decisions

| Decision | Approved choice |
|---|---|
| Model comparison | Dummy, logistic regression, XGBoost, and LightGBM; deploy only the accepted winner |
| MLflow | Private, local SQLite-backed tracking through an optional Compose profile |
| Research navigation | Visible, clearly labelled main-navigation area |
| Dropout data | Separate multi-condition longitudinal synthetic enrollment dataset |
| Cohort data | Unique synthetic patient snapshots × fixed approved reference-trial panel |
| Dropout fixture/demo/experiment sizes | 50 / 400 / 4,000 enrollments |
| Screening cohort | 750 unique patients × 20 reference trial versions |
| Condition portfolio | Metabolic, cardiovascular, renal, oncology, and respiratory |
| Observation cutoff and horizon | Day 30 cutoff; synthetic dropout through day 90 |
| Synthetic dropout prevalence | Approximately 25%, documented as a generator design choice |
| Scenario analysis | Missed-dose Scenario Lab with non-causal model-sensitivity wording |
| Cohort representations | Patient-fact space and screening-profile space |
| Cohort visualization | Seeded PCA initially; DBSCAN/FAISS operate in full feature space |
| Trial discovery | Required ClinicalTrials.gov API v2 retrieval plus cached fixtures |
| RAG | Bounded grounded generation over retrieved records with validated citations |
| Provider resilience | Groq cooldown, caching, concurrency control, bounded retry, and deterministic fallback |
| Local models | Not in the default TrialSync path |
| Delivery | GitHub Actions CI; manual health-gated deployment; automatic CD deferred |
| BioBERT | Deferred |

### Deliverables

- Approved version of this plan.
- A short claims matrix mapping each bootcamp requirement to the TrialSync implementation or documented substitution.
- Updated research findings that reflect the verified dataset conclusions.

### Exit criteria

- No disputed phase or claim remains implicit.
- The selected datasets and their different units of analysis are explicit.
- Provider failure behavior and out-of-scope features are explicit.
- The expected final demonstration is written down.
- No implementation has started before approval.

### Status

Complete. Begin R1 only; later phase approval does not authorize combining phases.

### Claims matrix

| Original requirement or presentation claim | TrialSync implementation or correction |
|---|---|
| Patient dropout prediction | Synthetic fixed-horizon dropout-risk demonstration; not real-world prediction |
| XGBoost and LightGBM | Compared with dummy and logistic baselines on the frozen synthetic dataset |
| SHAP explainability | Model contribution analysis only; never eligibility or causality |
| DBSCAN cohorts | Patient-fact and screening-profile clusters over unique synthetic patients |
| FAISS similarity | Exact cosine neighbors in versioned synthetic feature spaces |
| BioBERT matching | Deferred because no approved labelled matching task exists |
| RAG trial matching | Measured ClinicalTrials.gov retrieval plus bounded citation-validated comparison |
| LLM eligibility | Rejected; the deterministic engine remains authoritative |
| PDF report | Generated from canonical stored screening evidence |
| CI/CD | CI implemented; automatic CD deferred in favor of manual health-gated deployment |
| Production clinical platform | Corrected to research-grade academic prototype using synthetic participant data |

## 7. Phase R1 — Canonical screening report PDF

### Objective

Generate a reproducible, downloadable PDF from one stored screening without asking an LLM to recreate authoritative facts.

### Report contents

- TrialSync title and educational/synthetic-data disclaimer.
- Screening ID and creation timestamp.
- Overall cautious screening state.
- Patient snapshot label, version/hash, and as-of date.
- Trial title, registry label where applicable, approved version/hash.
- Engine and DSL versions.
- Pass/fail/unknown totals.
- One section or table row for every criterion:
  - criterion kind and source text;
  - stored result and reason code;
  - canonical explanation;
  - evidence values, units, effective dates, and source labels;
  - missing-information requirements;
  - rejected/stale evidence only where it materially explains `unknown`.
- Report-generation version and timestamp.
- Optional supplemental assistant summary only if explicitly enabled and clearly labelled non-canonical.

### Backend steps

1. Define a provider-neutral `ScreeningReportDocument` schema assembled from the stored screening detail contract.
2. Implement a pure report assembler that performs no screening and no provider calls.
3. Select a deterministic HTML-to-PDF or document-rendering library compatible with the backend image.
4. Create an authenticated endpoint:

   ```text
   GET /api/v1/screenings/{screening_id}/report.pdf
   ```

5. Enforce screening ownership before assembly.
6. Stream or return the PDF without persisting mutable report text on the screening row.
7. Generate a stable filename that contains no sensitive free text.
8. Add page-break handling, table continuation, long-criterion wrapping, and accessible HTML source where practical.
9. Record the report schema/template version in the document.

### Frontend steps

1. Add a labelled **Download report** action on saved screening details.
2. Provide loading, success, and explicit failure behavior.
3. Keep the structured browser evidence visible; downloading must not become the only way to inspect a result.
4. Do not add a report button to unsaved/import-review states.

### Tests

- Ownership and unauthenticated access.
- Correct content type and safe filename.
- All stored evaluations included exactly once.
- Pass, fail, unknown, and mixed cases.
- Missing evidence and stale evidence.
- Long criterion and long evidence labels.
- Unicode operators and units.
- Snapshot/trial/engine metadata.
- Deterministic assembly for the same stored screening.
- Provider-disabled behavior.
- Frontend download success and API failure.

### Visual review

- Desktop screening with mixed results.
- Narrow screening page containing the download action.
- Multi-page report.
- Long-text report.
- Unknown-heavy report.
- Print/PDF contrast and page breaks.

### Exit criteria

- The PDF is derived only from the authorized stored screening.
- The report agrees with the browser detail page.
- It works with Groq disabled.
- It contains no invented eligibility reasoning.
- Backend tests, frontend tests, production build, and visual review pass.

## 8. Phase R2 — GitHub Actions continuous integration

### Objective

Run the repository's existing quality gates automatically on pushes and pull requests.

### Steps

1. Add a least-privilege workflow under `.github/workflows/`.
2. Pin action major versions and document update policy.
3. Use service-container PostgreSQL or the existing Compose-compatible test path.
4. Install the pinned Python project and locked npm dependencies.
5. Run:
   - backend formatting/lint/type checks;
   - Alembic migration verification;
   - backend unit and integration tests;
   - frontend formatting/lint/type checks;
   - frontend tests;
   - frontend production build;
   - secret scanning or the existing safe audit subset;
   - optional container builds.
6. Cache only safe dependency directories; never cache `.env`, uploads, database files, model artifacts, or MLflow stores.
7. Ensure no workflow requires a Groq key.
8. Keep live provider evaluation manual and separately labelled.
9. Add job timeouts and concurrency cancellation for superseded branch runs.

### CI versus CD

This phase implements CI. It must not be called CD unless another approved phase publishes versioned images or deploys a saved release to a real target with verified rollback.

### Tests

- Reproduce every workflow command locally.
- Verify migrations against an empty database.
- Verify tests use deterministic providers.
- Verify no secret is required.
- Verify a deliberate test failure fails the job during development of the workflow.

### Exit criteria

- The full required gate passes in GitHub Actions.
- Local and CI commands are documented.
- Workflow logs contain no secrets or synthetic document contents.
- README badges, if added, link to the actual workflow.

## 9. Phase R3 — Synthetic longitudinal dropout protocol

### Objective

Create a reproducible event-level synthetic enrollment dataset for fixed-horizon dropout-risk
research and missed-dose scenario analysis. This dataset does not supply DBSCAN or FAISS data.

### 9.1 Research question

Primary:

> Within a generated clinical-trial participant cohort, can baseline and pre-cutoff operational/clinical features predict synthetic dropout before a declared follow-up horizon?

Scenario:

> How does the accepted model's output change when a plausible pre-cutoff dose event is changed
> from administered to missed, with every dependent feature recomputed?

### 9.2 Required time definitions

- `enrollment_day`: day 0.
- `observation_cutoff_day`: last day from which predictors may be drawn.
- `prediction_horizon_day`: future day by which dropout is classified.
- `dropout_day`: generated event day when dropout occurs.
- `censor_day`: last known follow-up when no dropout is observed.

No event after the observation cutoff may become a model feature.

### 9.3 Candidate synthetic variables

Static baseline variables:

- Synthetic participant ID.
- Age band or age.
- Sex where relevant to the simulated protocol.
- Disease category.
- Site/region category.
- Baseline functional severity.
- Baseline comorbidity burden.
- Baseline treatment burden.
- Travel/access burden.
- Assigned study arm.
- Condition category from the locked five-condition portfolio.

Pre-cutoff longitudinal variables:

- Scheduled, administered, and missed doses.
- Scheduled, attended, delayed, and missed visits.
- Missed-visit count.
- Visit-delay statistics.
- Functional/severity measurements.
- Selected normalized laboratory measurements.
- Adverse-event count and grade.
- Medication burden.
- Patient-reported burden.
- Measurement missingness.

Derived leakage-safe features:

- Baseline value.
- Latest pre-cutoff value.
- Pre-cutoff slope.
- Pre-cutoff variability.
- Pre-cutoff observation count.
- Missed-visit rate.
- Adverse-event burden.
- Data-missingness rate.

Outcomes:

- `dropout_within_horizon`.
- `dropout_day`.
- `dropout_reason` from a declared synthetic taxonomy.
- `censored`.

Required event tables:

- `research_participants`;
- `research_enrollments`;
- `research_dose_events`;
- `research_visit_events`;
- `research_measurements`;
- `research_adverse_events`;
- `research_outcomes`.

### 9.4 Generation principles

1. Use a fixed default seed plus configurable alternative seeds.
2. Separate the data-generating mechanism from the model-training pipeline.
3. Include stochastic noise and interactions.
4. Avoid a single deterministic "dropout score" column.
5. Avoid direct leakage such as final completion status, post-dropout visits, or future measurements.
6. Keep dropout prevalence plausible for the artificial scenario but label it as a design choice, not an empirical estimate.
7. Include controlled missingness and explain whether it is random or feature-dependent.
8. Define at least one deliberately nonlinear relationship so tree models have something meaningful to compare with logistic regression.
9. Preserve hidden generator state only for generator validation; do not export it as a model feature.
10. Generate only fictional values and identifiers.

### 9.5 Dataset sizes

Use three locked sizes:

- Tiny fixture: 50 enrollments for unit and schema tests.
- Demo cohort: 400 enrollments for the Scenario Lab and local inference.
- Experiment cohort: 4,000 enrollments for model comparison and stress evaluation.

Target approximately 25% synthetic dropout through day 90. Report the exact generated
prevalence and event counts for every split; never adjust the test set after inspection.

### 9.6 Split strategy

- Split by participant.
- Fit preprocessing on training data only.
- Prefer a generator-time or site-based holdout in addition to a random stratified split.
- Include a stress-test regime with changed coefficients or missingness.
- Freeze the primary test split before model tuning.
- Use repeated seeds or cross-validation only on training/validation data.

### 9.7 Artifacts and documentation

- Versioned dataset schema.
- Generator configuration.
- Feature dictionary.
- Outcome definition.
- Leakage audit.
- Data-quality report.
- Aggregate distributions and missingness report.
- Generator unit tests.
- Dataset card describing intended and prohibited uses.

### Tests

- Same seed produces identical checksums.
- Different seed changes participant values.
- IDs are unique and fictional.
- Dates follow the declared ordering.
- No post-cutoff feature leakage.
- Dropout labels agree with event times.
- Censoring is internally consistent.
- Values and units stay in declared artificial ranges.
- Train/validation/test participants do not overlap.
- Hidden generator labels are excluded from exported model features.
- Missed-dose scenario edits recompute every dependent adherence feature.

### Exit criteria

- The dataset card and feature dictionary are understandable without reading generator code.
- Leakage tests pass.
- Outcome prevalence and split event counts are reported.
- The user approves the artificial assumptions before model training begins.

### Stop point

Pause for review of the generated dataset report before implementing model experiments.

## 10. Phase R4 — Dropout model experiments, MLflow, and SHAP

### Objective

Build a reproducible offline research pipeline comparing interpretable and tree-based classifiers on the approved synthetic dataset.

### Model sequence

1. Dummy prevalence baseline.
2. Logistic regression baseline.
3. XGBoost classifier.
4. LightGBM classifier.

Run both locked tree-model comparisons. Only the accepted winner is exposed through the later
risk API.

### Pipeline requirements

- One versioned feature builder shared by training and inference.
- Explicit categorical/numeric preprocessing.
- Training-only imputation and scaling.
- Class-imbalance handling selected from training data only.
- Fixed random seeds.
- Bounded hyperparameter search.
- No tuning on the test split.
- Serialized pipeline includes preprocessing and model.
- Model metadata includes dataset, generator, split, feature, code, and dependency versions.

### Metrics

Required:

- Event prevalence and event counts.
- AUROC.
- AUPRC.
- Log loss or Brier score.
- Calibration curve and calibration error.
- Sensitivity and specificity at a declared threshold.
- Precision, recall, and F1 at that threshold.
- Confusion matrix.
- Bootstrap or repeated-split uncertainty where practical.

Subgroup reporting on synthetic categories may demonstrate evaluation plumbing, but it must not be presented as a fairness or clinical-validity conclusion.

### Threshold policy

- Select a threshold using validation data and a declared research objective.
- Store the threshold with the model version.
- Do not use 0.5 merely by default without reporting why.
- Never translate the threshold into eligibility.

### MLflow

Track:

- Run ID and timestamps.
- Dataset and generator versions/checksums.
- Split version.
- Feature schema version.
- Code commit when available.
- Parameters and seeds.
- Metrics and curves.
- Serialized pipeline.
- Model signature and input example.
- Dependency environment.
- Tags describing synthetic-only intended use.

Use the locked private, local SQLite-backed MLflow store through its optional Compose profile.
Do not add a remote tracking service as a hidden requirement.

Model aliases:

- `candidate` for models under evaluation.
- `champion` only after acceptance criteria pass.

### SHAP

- Use the appropriate explainer for the selected tree model.
- Produce global summary plots and per-prediction contributions.
- Map transformed features back to stable display labels.
- Clearly distinguish feature contribution from causal effect.
- Bound the number of displayed features.
- Test behavior for missing and categorical values.

### Acceptance criteria

Because the data are synthetic, acceptance must focus on pipeline correctness and reproducibility rather than impressive scores:

- Training is reproducible within documented tolerance.
- The final model beats the dummy baseline on the frozen synthetic test set.
- Calibration is reported and not hidden.
- Inference schema validation is strict.
- SHAP contributions reconcile with the model output within library tolerance.
- A simple logistic baseline remains visible beside the tree model.
- Known generator signal recovery is discussed without claiming real-world validity.

### Tests

- Feature parity between training and inference.
- No test-data fitting.
- Repeated training reproducibility.
- Artifact load and predict.
- Invalid/missing schema rejection.
- Threshold metadata round trip.
- MLflow run metadata completeness.
- SHAP output finiteness and feature-label mapping.
- No screening-domain imports or mutations.

### Exit criteria

- One model is promoted to the local `champion` alias.
- The evaluation report includes all required metrics and limitations.
- The model can be loaded in a clean process and reproduce inference.
- No prediction is described as clinically validated.

### Stop point

Pause for user approval of metrics, model choice, threshold, and presentation wording before adding runtime inference.

## 11. Phase R5 — Versioned research-risk API and UI

### Objective

Expose the accepted synthetic model through a separate authenticated research interface without coupling it to deterministic screening.

### Data model

Candidate entities:

- `research_model_versions`
  - model name/version/alias;
  - dataset and feature schema versions;
  - threshold;
  - validation status;
  - safe aggregate metrics;
  - artifact locator/checksum;
  - created timestamp.
- `research_predictions`
  - owner;
  - synthetic research subject ID or approved demo-patient mapping;
  - model version;
  - feature snapshot JSON/hash;
  - probability;
  - thresholded research label;
  - top SHAP contributions;
  - prediction timestamp;
  - synthetic/research disclaimer version.

Do not attach mutable risk fields to `screenings` or `patients`.

### API

Candidate routes:

```text
GET  /api/v1/research/risk/models
GET  /api/v1/research/risk/models/{model_version}
POST /api/v1/research/risk/predictions
GET  /api/v1/research/risk/predictions
GET  /api/v1/research/risk/predictions/{prediction_id}
```

Example response:

```json
{
  "risk_type": "synthetic_trial_dropout",
  "probability": 0.64,
  "threshold": 0.58,
  "research_label": "higher_synthetic_risk",
  "horizon_day": 90,
  "model": {
    "name": "dropout-lightgbm",
    "version": "1",
    "alias": "champion"
  },
  "top_contributions": [
    {
      "feature": "missed_visit_rate_pre_cutoff",
      "value": 0.25,
      "shap_value": 0.18
    }
  ],
  "disclaimer": "Synthetic research prediction; not a clinical or eligibility decision."
}
```

### Runtime rules

- Load an explicitly configured approved model version.
- Validate the feature schema before inference.
- Fail readiness only for the optional research capability, not the core API.
- Record model/dataset/feature versions with every prediction.
- Do not call Groq.
- Do not trigger screening.
- Do not convert probability into `potentially_eligible`, `likely_ineligible`, or `needs_review`.
- Do not permit prediction creation for arbitrary real records.

### Frontend

Create a clearly labelled research area:

- Research overview with synthetic-data boundary.
- Model card with dataset, horizon, metrics, threshold, and limitations.
- Synthetic participant selector or form.
- Risk result with probability, threshold, and top SHAP contributions.
- Link to model version and feature definitions.
- Clear separation from the screening workspace.

Avoid:

- Red/green eligibility styling for research risk.
- Alarmist labels such as "will drop out."
- Treatment or retention recommendations.
- Hiding model limitations in a tooltip.

### Tests

- Authentication and ownership.
- Approved-model loading.
- Missing artifact/degraded capability.
- Schema mismatch.
- Stable prediction for fixed input.
- Prediction persistence and version metadata.
- SHAP contribution display.
- Core screening equivalence before and after prediction.
- Provider/network-disabled behavior.
- UI loading, populated, invalid-input, artifact-missing, and API-error states.

### Visual review

- Research overview.
- Model card.
- Low, near-threshold, and high synthetic probabilities.
- Long feature names.
- Missing model artifact.
- Narrow layout.
- Keyboard focus and reduced motion.

### Exit criteria

- A prediction cannot mutate any screening record.
- Every display says synthetic/research-only.
- Model and feature versions are reproducible.
- Core application tests still pass unchanged.
- Full build and required visual review pass.

## 12. Phase R6 — Screening-derived cohorts, FAISS similarity, and Cohort Atlas

### Objective

Build a research-only cohort explorer from unique synthetic patient snapshots and their
deterministic evidence profiles across a fixed panel of approved trial versions. This phase
does not use the R3 dropout dataset.

### Cohort materialization

1. Generate 750 unique multi-condition synthetic patients through the existing patient/fact
   schema with a fixed seed.
2. Define a reference panel of 20 approved synthetic trial versions.
3. Call the exact pure single-screening engine for each patient × trial pair.
4. Materialize 15,000 deterministic evaluations into a versioned research matrix without
   adding 15,000 rows to ordinary screening history.
5. Collapse the matrix to one sample per unique patient.
6. Record patient, trial-panel, criterion-order, engine, DSL, terminology, unit, and
   materialization checksums.

The sample size is 750 patients, not 15,000 screening pairs.

### Feature representations

Create two separately versioned spaces:

1. **Patient-fact space**
   - age band and demographic fields;
   - condition and medication assertions;
   - normalized compatible observations;
   - evidence age and missingness.
2. **Screening-profile space**
   - one-hot pass/fail/unknown criterion results;
   - result rates by trial and criterion family;
   - missing-information categories;
   - result patterns across the frozen reference panel.

`unknown` must be one-hot encoded and must never be treated as numerically halfway between pass
and fail.

Do not use dropout outcomes, dropout-model risk, SHAP values, hidden generator classes, mutable
chat text, or RAG summaries in either representation.

### DBSCAN steps

1. Fit preprocessing separately for the two approved representations.
2. Inspect distance distributions.
3. Select a bounded parameter grid for `eps` and `min_samples`.
4. Record cluster count, cluster sizes, and noise fraction.
5. Report silhouette score only where mathematically meaningful.
6. Evaluate stability across bootstrap samples, seeds, or nearby parameters.
7. Inspect condition composition after patient-fact clustering to identify trivial
   disease-category separation.
8. Label screening-profile groups as evidence profiles, not clinical phenotypes.
9. Use neutral identifiers such as `fact_cluster_0` and `screening_cluster_0`.

K-means may be included as a baseline comparison but does not replace DBSCAN unless the user explicitly changes the bootcamp mapping.

### FAISS steps

1. Produce normalized dense vectors for both versioned representations.
2. Build one exact CPU index per representation using normalized inner product for cosine
   similarity.
3. Store:
   - representation name;
   - cohort and reference-panel checksums;
   - embedding version;
   - preprocessing version;
   - index type;
   - vector dimension;
   - subject ordering/mapping checksum;
   - build timestamp.
4. Exclude the query subject from its own neighbor list.
5. Return distance/similarity plus a transparent feature comparison.
6. Rebuild both indexes explicitly when patients, facts, trial versions, criteria, engine
   versions, or preprocessing change.

### API

Candidate routes:

```text
GET  /api/v1/research/cohorts/runs
GET  /api/v1/research/cohorts/runs/{run_id}
GET  /api/v1/research/cohorts/runs/{run_id}/clusters
POST /api/v1/research/similarity/queries
GET  /api/v1/research/similarity/queries/{query_id}
```

### Frontend

- Cohort Atlas with a patient-fact/screening-profile representation switch.
- Seeded PCA projection for display only; DBSCAN and FAISS stay in full feature space.
- One patient node per unique snapshot, neutral noise nodes, and restrained cluster colors.
- FAISS edges only from the selected patient to its nearest neighbors.
- Cluster-size and noise summary.
- Structured participant table with cluster filters.
- Similar-patient side panel with exact fact or criterion-state differences.
- Links from screening-profile dimensions to canonical criterion evidence.
- Prominent statement that similarity is not eligibility evidence.

### Tests

- Same patient/reference-panel seeds produce identical matrix checksums.
- 15,000 evaluations collapse to exactly 750 cohort members.
- Materialized results agree with direct calls to the single-screening engine.
- Patient-fact and screening-profile representations remain distinct.
- `unknown` is one-hot encoded.
- No dropout, risk, SHAP, chat, or RAG leakage.
- DBSCAN noise handling.
- Parameter/stability report generation.
- FAISS vector normalization.
- Self-match exclusion.
- Exact-neighbor agreement with brute-force cosine similarity.
- Index-version mismatch rejection.
- Missing index degraded state.
- PCA projection is reproducible and does not become the similarity source of truth.
- Core screening remains unchanged.

### Visual review

- No-cluster/all-noise run.
- Multiple-cluster run.
- Small and large cluster.
- Patient-fact and screening-profile views.
- Selected patient with neighbor edges and evidence comparison.
- Similarity results with tied scores.
- Long feature comparison.
- Narrow layout, focus, reduced motion, loading, and error states.

### Exit criteria

- Both cohort representations use unique patient-level samples and documented features.
- Stability, noise, and condition-composition checks are reported.
- Both exact similarity indexes are reproducible and versioned.
- The Cohort Atlas states that 2D position is approximate and full-space similarity is exact.
- No cluster or neighbor is used as screening evidence.
- Research disclaimers remain visible.

## 13. Phase R7 — ClinicalTrials.gov discovery and genuine RAG

### Objective

Add public trial discovery, measured criterion retrieval, and a bounded generation step over retrieved trial context before the existing reviewed import and deterministic screening workflow.

### Source

Use the official ClinicalTrials.gov API v2. Do not depend on an unspecified Kaggle snapshot.

### Source adapter

The adapter should retrieve and normalize:

- NCT identifier.
- Brief and official title.
- Overall recruitment status and verification date.
- Conditions.
- Study type and phase where available.
- Locations where required by the query.
- Minimum/maximum age and sex fields.
- Full eligibility text.
- Last update/source timestamp.
- Raw-record checksum.

### Retrieval sequence

```text
Coordinator query or approved synthetic patient summary
  -> deterministic filters
  -> text retrieval/ranking
  -> candidate trials with score and source metadata
  -> bounded LLM summary over only the retrieved records
  -> validate every generated NCT/criterion citation
  -> coordinator selects a trial
  -> existing review-first criterion extraction
  -> explicit approval of a trial version
  -> existing deterministic screening
```

### Ranking

Start with a reproducible baseline:

- Structured condition/status/age filters.
- BM25 or another documented local lexical ranking method.
- Optional embedding reranker only after a held-out retrieval set exists.

FAISS from R6 must not automatically become the trial-retrieval index; participant similarity and trial retrieval have different corpora and evaluation questions.

### Storage

Candidate entities:

- `trial_source_records`
  - source;
  - NCT ID;
  - source timestamp;
  - fetched timestamp;
  - checksum;
  - normalized public fields;
  - raw response or bounded source snapshot according to storage decision.
- `trial_retrieval_runs`
  - owner;
  - query;
  - filters;
  - retriever/index version;
  - timestamps.
- `trial_retrieval_results`
  - run;
  - source record;
  - rank;
  - score;
  - explanation of matched fields.

### API

Candidate routes:

```text
POST /api/v1/trial-discovery/search
GET  /api/v1/trial-discovery/runs/{run_id}
POST /api/v1/trial-discovery/results/{result_id}/create-review
```

Creating a review copies the selected source record into the existing unapproved import/review boundary. It does not create an approved trial or screening.

### Required RAG contract

R7 is genuine RAG only when:

- a corpus/index exists;
- retrieval is a distinct measured step;
- retrieved criterion context is supplied to a bounded extractor or explainer;
- source IDs and versions are retained;
- generated claims cite retrieved NCT/criterion identifiers and are rejected when those citations are invalid;
- retrieval quality and generated-answer grounding are evaluated separately.

The generated artifact should be a schema-validated, query-scoped trial-discovery summary. It may explain why a retrieved record matched the query, quote bounded eligibility excerpts, and identify missing query information. It may not approve a trial, create screening evidence, claim eligibility, or bypass the existing review flow.

The RAG context is assembled server-side from only the top bounded retrieved records. Retrieved text and user queries are untrusted data. The provider receives no database, web, MCP, code-execution, or write tools. A deterministic ranked-results view remains available when the provider is disabled, times out, is rate-limited, or returns an invalid response.

LangChain is not required. Direct adapters are preferred when they are easier to test and version.

### Groq 429 resilience

Strengthen the existing structured client rather than routing failures to a local small model:

1. Parse numeric and HTTP-date `Retry-After` values.
2. Maintain an in-process `next_allowed_at` cooldown for the single production backend
   process.
3. Limit concurrent Groq requests with an async semaphore.
4. Retry once only when the delay is short and remains inside the request deadline.
5. Add bounded jitter for retryable 5xx/timeout responses.
6. Cache public-trial RAG summaries by query/filter, corpus, retriever, model, and prompt
   versions.
7. Preserve the existing redacted-checksum extraction cache contract.
8. Never cross-user cache patient-specific explanation answers.
9. Return explicit degraded/rate-limited metadata and a safe retry time.
10. Fall back by operation:
    - extraction → deterministic candidates and human review;
    - screening chat → canonical criterion explanations;
    - RAG → deterministic ranked trial results;
    - eligibility → unchanged deterministic engine.

No Redis, queue, local LLM, or retry storm is introduced.

### Retrieval and grounding evaluation

Create a synthetic or manually curated query set containing expected relevant trials or conditions. Report:

- Recall@k.
- Precision@k where labels permit.
- Mean reciprocal rank.
- Filter correctness.
- Stale/source-version behavior.
- Failure and rate-limit handling.
- Generated citation validity.
- Grounded-claim precision.
- Unsupported-claim count.
- Prompt-injection resistance.
- Deterministic fallback behavior.

These metrics evaluate retrieval and grounded generation, not patient eligibility.

### Tests

- API response-schema fixtures.
- Pagination.
- Rate limiting, timeout, invalid response, and no-results behavior.
- Source timestamps and checksums.
- Filter correctness.
- Duplicate NCT version handling.
- Retrieval determinism for a frozen fixture corpus.
- Retrieved-context bounds and ordering.
- Valid, missing, and fabricated generated citations.
- Unsupported generated claims and prompt injection.
- Provider-disabled, timeout, rate-limit, and invalid-schema fallbacks.
- Numeric/date `Retry-After`, cooldown, concurrency, cache, and no-retry-storm behavior.
- Review creation preserves source metadata.
- No automatic approval or screening.

### Frontend

- Trial discovery form with clear public-source label.
- Ranked results with recruitment status, verification date, and matched fields.
- A clearly labelled generated summary with validated links to its retrieved NCT records and criterion excerpts.
- No-results and source-unavailable states.
- Provider-disabled and invalid-generated-summary states that preserve deterministic ranked results.
- Select-for-review action.
- Existing side-by-side review flow for selected criteria.

### Visual review

- Populated, no-results, API-error, stale-record, long-eligibility, grounded-summary, provider-degraded, and narrow states.
- Keyboard navigation and focus.
- Reduced motion.

### Exit criteria

- Public source provenance is reproducible.
- Retrieval is measured separately from screening.
- The bounded generator receives only retrieved context and every substantive generated claim has a validated source citation.
- Retrieval and grounding evaluations pass their declared acceptance thresholds.
- Selected trials always pass through human review and approval.
- Provider/source failure preserves cached/frozen retrieval fixtures and does not break manual trial creation.
- Repeated requests during provider cooldown do not call Groq.

## 14. Phase R8 — Integrated evaluation and final delivery

### Objective

Demonstrate the extension coherently, reproduce it from a clean environment, and align every presentation claim with evidence.

### Required evaluation package

1. Core deterministic screening regression results.
2. Canonical PDF consistency checks.
3. CI workflow evidence.
4. Synthetic dataset card and leakage audit.
5. Dropout model comparison:
   - dummy;
   - logistic regression;
   - XGBoost;
   - LightGBM.
6. Calibration and selected threshold.
7. MLflow run/registry evidence.
8. SHAP global and local explanation examples.
9. Patient-fact and screening-profile DBSCAN parameter/stability reports.
10. Both FAISS exact-neighbor verifications and Cohort Atlas projection evidence.
11. ClinicalTrials.gov retrieval and grounded-generation metrics.
12. Groq cooldown/cache/retry and full offline/degraded-mode behavior.
13. Security, dependency, and secret checks.

### Final demonstration script

1. Open the seeded synthetic workspace.
2. Show a patient snapshot and approved trial version.
3. Run or open a deterministic screening.
4. Explain one pass, fail, and unknown criterion from stored evidence.
5. Download the canonical PDF and show that it matches the result page.
6. Open the research area and state the synthetic-data boundary.
7. Show the approved dropout model card and comparison with the logistic baseline.
8. Run one synthetic dropout-risk prediction.
9. Explain the top SHAP contributions without causal language.
10. Switch the Cohort Atlas between patient-fact and screening-profile views, show noise
    handling, and inspect one FAISS neighbor comparison.
11. Retrieve public trials, show the citation-validated RAG summary, and send one result through review.
12. Show that neither risk, cluster, similarity, retrieval, nor LLM output changes eligibility.
13. Show CI evidence and the offline/manual fallback.

### Documentation updates

- Root README.
- Architecture document.
- Research dataset card.
- Feature dictionary.
- Model card.
- Research evaluation report.
- Limitations and claims matrix.
- API examples/OpenAPI.
- Screenshots.
- Presentation notes.

### Final verification

- Fresh setup and migration.
- Synthetic data generation.
- Model training or documented artifact restoration.
- MLflow run visibility.
- Backend formatting, linting, type checks, tests.
- Frontend formatting, linting, type checks, tests, build.
- Browser end-to-end workflows.
- Docker/Compose validation.
- GitHub Actions success.
- Dependency and secret audit.
- No generated research artifact or restricted data accidentally tracked.
- No local language model is required by the clean setup or live demonstration.

### Exit criteria

- Every approved phase has reproducible evidence.
- The project works without Groq and without live ClinicalTrials.gov access.
- Core screening remains deterministic and unchanged.
- Research outputs are clearly synthetic and versioned.
- No final claim exceeds the implemented evaluation.

## 15. Cross-phase database and migration rules

- Add one Alembic revision per bounded schema phase.
- Research migrations must not rewrite immutable screening history.
- Avoid large opaque model binaries in PostgreSQL.
- Store artifact metadata/checksums and use an explicit local artifact directory.
- Validate artifact presence and checksum before loading.
- Preserve user ownership on all runtime research records.
- Keep training-run aggregates separate from per-user inference history.
- Provide downgrade behavior where safe and test upgrades from the current head.

## 16. Cross-phase testing rules

For every behavioral phase:

1. Add narrow unit tests first.
2. Add PostgreSQL integration tests for persistence/API changes.
3. Add frontend tests for new user-visible states.
4. Add or update browser workflows for material UI changes.
5. Run targeted checks.
6. Run the full applicable backend and frontend gates.
7. Run the production frontend build.
8. Inspect desktop and narrow screenshots.
9. Check loading, empty, error, populated, long-text, and unknown/degraded states.
10. Verify keyboard focus and reduced motion.

No automated test may:

- call Groq;
- depend on live ClinicalTrials.gov;
- download a restricted dataset;
- depend on a mutable remote model registry;
- send synthetic document contents to an external service.

## 17. Cross-phase observability rules

Safe fields:

- Request/trace ID.
- Route, status, and duration.
- Dataset/generator/feature/model/index versions.
- Aggregate training metrics.
- Prediction duration and model version.
- Retrieval duration, result count, and source version.
- Report template version and duration.

Never log:

- API keys or tokens.
- Full patient or document text.
- Raw research feature rows tied to user identities.
- Raw provider payloads.
- Generated PDF contents.
- Model artifacts.

## 18. Dependency policy

Potential new dependencies must be approved during their phase. Expected categories include:

- Deterministic PDF rendering.
- pandas/NumPy or equivalent bounded tabular tooling.
- scikit-learn.
- XGBoost.
- LightGBM.
- MLflow.
- SHAP.
- FAISS CPU.
- A lexical retrieval library if the standard library or existing dependencies are insufficient.

Before adding a dependency:

- confirm Python 3.12 support;
- inspect license and maintenance status;
- confirm container compatibility;
- record why an existing dependency is insufficient;
- pin or lock it;
- add an audit path;
- avoid pulling in a second framework for one small helper.

## 19. Suggested commits

One possible history:

```text
docs: approve TrialSync research extension plan
feat: add canonical screening PDF reports
ci: add backend and frontend verification workflow
feat: add reproducible synthetic participant generator
feat: add dropout model experiments and MLflow tracking
feat: add versioned synthetic risk inference
feat: add research cohort and similarity explorer
feat: add ClinicalTrials.gov discovery and genuine RAG
test: complete research extension evaluation
docs: finalize research report and presentation
```

Commits are phase checkpoints, not permission to combine several phases into one implementation pass.

## 20. Final scope audit

- [x] R1–R8 remain separate bounded phases.
- [x] BioBERT, restricted-data dependencies, automatic CD, and local-LLM fallback are deferred.
- [x] Dropout and cohort/similarity use different datasets and units of analysis.
- [x] Dummy, logistic, XGBoost, and LightGBM are compared before champion selection.
- [x] MLflow uses a private optional Compose profile.
- [x] Research analytics appear in labelled main navigation.
- [x] Dropout uses day 30 → day 90 over 50/400/4,000 synthetic enrollments.
- [x] Cohort analysis uses 750 unique patients × 20 fixed reference trials.
- [x] The Scenario Lab presents model sensitivity, never causality.
- [x] The Cohort Atlas supports patient-fact and screening-profile representations.
- [x] ClinicalTrials.gov genuine RAG is required with cached fixtures.
- [x] Groq 429 handling uses cooldown/cache/concurrency/fallback instead of local models.
- [x] CI is required and deployment remains manual and health-gated.
- [x] Every research output remains separate from deterministic eligibility.

## 21. Phase status tracker

| Phase | Status | Approval evidence | Exit evidence |
|---|---|---|---|
| R0. Scope lock | Complete | Locked decisions and claims matrix approved 2026-07-26 | This document |
| R1. Canonical report PDF | Approved | User selected evidence-backed reporting, 2026-07-26 | |
| R2. GitHub Actions CI | Approved | User selected supporting engineering delivery, 2026-07-26 | |
| R3. Synthetic dropout protocol/dataset | Approved | User selected dropout-risk modeling, 2026-07-26 | |
| R4. Dropout models/MLflow/SHAP | Approved | User selected dropout-risk modeling, 2026-07-26 | |
| R5. Research-risk API/UI | Approved | User selected research delivery surface, 2026-07-26 | |
| R6. Screening-derived DBSCAN/FAISS cohorts | Approved | User selected cohort analytics, 2026-07-26 | |
| R7. ClinicalTrials.gov genuine RAG | Approved | User explicitly selected genuine RAG, 2026-07-26 | |
| R8. Evaluation/final delivery | Approved | User selected supporting engineering/evaluation, 2026-07-26 | |

Allowed statuses: `Awaiting review`, `Approved`, `Revise`, `Not authorized`, `In progress`, `Blocked`, `Complete`, `Skipped`, or `Deferred`.

R0 is complete. Begin R1 only and preserve every later stop point.

## 22. Implementation handoff format

Every later phase should end with:

```text
Phase completed:

Outcome:

Files changed:

Behavior/API/data changes:

Tests and builds run:

Visual states inspected (if frontend changed):

Known limitations:

Exit criteria not yet satisfied:

Recommended next task:
```

No phase is complete merely because files exist. Completion requires its observable behavior, tests, builds, documentation, visual review where applicable, and exit criteria to pass.
