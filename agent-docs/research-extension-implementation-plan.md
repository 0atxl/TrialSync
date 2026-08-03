# TrialSync Research Extension: Phased Implementation Plan

**Date:** 2026-07-24
**Status:** R0 revised and re-locked on 2026-07-26 after alignment with the supplied
LangChain/Gemini RAG and GitHub Actions brief; the R3 data strategy was clarified on
2026-08-01; R1 completed on 2026-08-02; R2 CI completed on 2026-08-02; automated CD is
deferred until the deployment target and release frequency justify it.
**Relationship to the current application:** Incremental extension after the completed deterministic TrialSync workflow. This plan does not replace the existing architecture or reopen completed rebuild phases.

## 1. Purpose

This document is the authoritative implementation sequence for **TrialSync: Clinical Trial
Patient Matching and Dropout Prediction**. It evolves the completed explainable matching product
into a broader, testable clinical-research platform while preserving deterministic eligibility as
the trusted matching core.

The approved extension contains:

1. Canonical evidence-backed PDF reporting and GitHub Actions CI, with automated CD deferred.
2. A separate, auditable longitudinal enrollment generator for dropout-risk research, with
   optional NVIDIA NeMo Data Designer orchestration and a future external benchmark adapter if
   suitable row-level data becomes legitimately accessible.
3. Logistic regression, XGBoost, LightGBM, MLflow, SHAP, and a missed-dose Scenario Lab.
4. A screening-derived patient cohort for DBSCAN clustering, FAISS similarity, and the
   Cohort Atlas.
5. LangChain retrieval over approved, versioned trial eligibility criteria with a
   Gemini-generated structured eligibility summary and citation validation.
6. Integrated evaluation, documentation, and presentation evidence.

The feasibility evidence and rationale are recorded in
[`research-pivot-findings.md`](research-pivot-findings.md) and
[`research-feasibility-rating-and-local-llm.md`](research-feasibility-rating-and-local-llm.md).

The extension has two distinct surfaces:

```text
TrialSync patient-matching core
  -> reviewed patient/trial inputs
  -> deterministic pass/fail/unknown screening
  -> canonical evidence and downloadable report

TrialSync research analytics
  -> hybrid statistical/synthetic longitudinal enrollment dataset
  -> dropout-risk experiments and Scenario Lab
  -> screening-derived patient cohort
  -> DBSCAN clustering, FAISS similarity, and Cohort Atlas
  -> patient-record-to-criteria RAG and grounded eligibility summary
  -> clearly separated research outputs
```

The deterministic screening result remains the source of truth for patient–trial matching. Research predictions, clusters, similarity results, SHAP values, retrieval scores, and LLM prose enrich the workflow with retention, discovery, and explanatory insight; they must never change eligibility.

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

- GitHub Actions CI is implemented; automated CD is deferred and manual Compose deployment
  remains the current delivery path.
- No hybrid longitudinal enrollment generator or frozen dropout-research dataset.
- No screening-derived patient cohort/reference-trial matrix.
- No dropout-risk model, model registry, calibration report, or SHAP explanation.
- No research-risk inference API or UI.
- No patient-fact or screening-profile clustering/similarity experiment.
- No FAISS index.
- No LangChain eligibility-criteria retriever, Gemini structured-summary provider, or RAG evaluation.
- No research-extension evaluation/reporting package.

## 3. Fixed decisions

These decisions apply to every phase unless the user explicitly changes them after reviewing this document.

### 3.1 Data boundary

- The repository, automated tests, demo, Groq requests, screenshots, and downloadable reports use fictional synthetic participant data only.
- The public, reproducible longitudinal dropout dataset is generated specifically for this
  project with fixed seeds and documented causal assumptions. Its structured events and outcome
  labels come from an auditable stochastic simulator, not directly from an LLM.
- NVIDIA NeMo Data Designer may orchestrate approved samplers, expressions, validation, and
  optional fictional narrative fields. It is not the authority for eligibility, dropout labels,
  hidden hazard coefficients, dataset splits, or evaluation ground truth.
- The cohort dataset is generated from unique synthetic patient snapshots evaluated against
  a fixed, versioned panel of approved synthetic trial versions.
- MIMIC-III, PRO-ACT, n2c2, NCT02054715-D1, and Project Data Sphere are not runtime, build,
  test, public-demo, or clean-reproduction dependencies.
- The public NCT02054715-D1 material currently verifies a useful study-specific schema, including
  genuine participant dropout fields, but does not include downloadable participant rows. The
  study is not in NCI's current dbGaP availability list as of 2026-08-01. If row-level data later
  becomes legitimately accessible, it may be evaluated as a separate benchmark; it is never
  merged into the public synthetic cohort or used to broaden claims beyond that oncology
  psychoeducation study.
- Restricted rows, prompts derived from them, and potentially governed derivatives must not be
  sent to NVIDIA or any other hosted model endpoint without explicit data-use and institutional
  approval. No restricted or NCT-derived row or model artifact belongs in Git or the public demo.
- The RAG corpus is built from approved, versioned trial criteria already stored in TrialSync
  plus checked-in synthetic trial fixtures; it does not require a live external trial registry.

### 3.2 Product-integrity boundary

- Eligibility remains deterministic.
- A dropout probability is not an eligibility score.
- A cluster is not a diagnosis or trial recommendation.
- Similar patients are not screening evidence.
- A retrieval score is not proof of eligibility.
- SHAP explains a model output; it does not establish causality.
- LLM text supplements canonical stored results; it does not create the canonical result.

### 3.3 Product boundary

- Research analytics live in a visibly labelled research area.
- The research frontend includes a **Trial Recruitment Overview** that groups saved screenings by approved trial version. Selecting a trial shows its potentially eligible, needs-review, and likely-ineligible counts, then a compact retention chart showing how many linked, potentially eligible research participants are in each dropout-risk band.
- The retention chart is an operational planning view, not a new eligibility result. It requires an explicit, versioned linkage between a screening snapshot and the longitudinal research participant/trial context; no count may be inferred by joining unrelated screening and dropout cohorts.
- Existing screening contracts remain backward compatible unless a phase explicitly documents a versioned addition.
- The core application continues to work when research dependencies, MLflow, FAISS, Gemini, or Groq are unavailable.
- No queue, Redis, Celery, microservice, Kubernetes, vector database, billing system, or EHR integration is introduced.
- Ollama and local language models are not part of TrialSync's default provider path.
- Gemini is used for the required RAG eligibility summary; Groq remains the existing optional
  extraction/chat provider. Criteria retrieval, canonical explanations, and screening continue
  to work during provider cooldown or failure.

### 3.4 Claim boundary

Allowed claims:

- "Synthetic dropout-risk modeling demonstration."
- "Study-specific retention-risk benchmark on NCT02054715-D1" only after participant rows become
  legitimately accessible and a completed held-out evaluation exists.
- "Research-only cohort discovery over generated patient profiles."
- "Similarity in a versioned synthetic feature space."
- "RAG-assisted matching over approved, versioned trial eligibility criteria."
- "Evidence-backed deterministic pre-screening."

Disallowed claims:

- "Predicts whether real clinical-trial participants will drop out."
- "Clinically validated dropout model."
- "Discovers real disease phenotypes."
- "Automatically determines trial eligibility."
- "Production clinical platform."
- "HIPAA compliant" or "hospital ready."
- "Continuous deployment" before the configured target, protected environment, health gate,
  and rollback path are implemented and tested.

### 3.5 Selected scope

Approved for inclusion:

- Canonical evidence-backed screening PDF reports.
- GitHub Actions continuous integration; manual health-checked deployment to the configured
  target for now. Automated CD is deferred until it is needed.
- A versioned synthetic longitudinal participant dataset.
- An optional, separately versioned NCT02054715-D1 adapter and evaluation report if participant
  rows become legitimately accessible; the public application remains reproducible without it.
- Logistic-regression, XGBoost, and LightGBM dropout-risk experiments with MLflow and SHAP.
- A separate research-risk API and UI.
- A trial-centric recruitment and retention overview, including grouped screening counts and an aggregate dropout-risk chart for explicitly linked research participants.
- DBSCAN cohort discovery and FAISS participant similarity.
- LangChain retrieval over approved trial criteria plus a schema-validated Gemini eligibility summary.
- Integrated evaluation, documentation, and presentation evidence.

Deferred:

- BioBERT clinical extraction or patient–criterion matching.
- Restricted patient-level datasets as runtime, build, test, or public-demo dependencies.
- Local small-model fallback for Gemini or Groq failures.

## 4. Proposed final architecture

```text
backend/src/trialsync/
  reports/                    # canonical screening report assembly/rendering
  research/
    dropout_data/            # longitudinal enrollment generation and validation
    dropout_features/        # leakage-safe fixed-horizon features
    external_validation/     # optional restricted-data adapters; no governed rows in Git
    risk/                    # training, evaluation, registry, inference
    cohort_profiles/         # patient facts and screening-profile matrices
    cohorts/                 # DBSCAN, stability, projections, summaries
    similarity/              # FAISS index build/query and metadata
    eligibility_rag/         # LangChain criteria retrieval and Gemini structured summaries
    provider_resilience/     # Gemini/Groq cooldown, cache, concurrency, and fallbacks

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
 +--> R2 GitHub Actions CI (CD deferred)
 |
 +--> R3 Synthetic longitudinal dropout protocol and dataset
       -> R4 Dropout model experiments
             -> R5 Versioned risk API and Scenario Lab
 |
 +--> R6 Screening-derived cohorts, DBSCAN, FAISS, and Cohort Atlas
 |
 +--> R7 Eligibility-criteria RAG with LangChain and Gemini
 |
 +--> R8 Integrated evaluation, documentation, and presentation
```

R1 and R2 may proceed independently after R0. R4 depends on the accepted R3 longitudinal
dropout dataset, and R5 depends on an R4 model passing its declared acceptance criteria. R6
uses a different screening-derived patient cohort and does not depend on the dropout dataset.
R7 is independent of both research datasets and uses the existing approved trial versions as
its retrieval corpus.

## 6. Phase R0 — Scope lock and research protocol

### Objective

Record the approved extension boundaries and prevent later phases from silently expanding them.

### Locked decisions

| Decision | Approved choice |
|---|---|
| Model comparison | Dummy, logistic regression, XGBoost, and LightGBM; deploy only the accepted winner |
| MLflow | Private, local SQLite-backed tracking through an optional Compose profile |
| Research navigation | Visible, clearly labelled main-navigation area |
| Dropout data | Separate multi-condition longitudinal dataset from an audited stochastic simulator; optional NeMo Data Designer orchestration |
| External dropout benchmark | NCT02054715-D1 public schema now; row-level evaluation only if the participant data becomes legitimately accessible, with separate artifacts and claims |
| Cohort data | Unique synthetic patient snapshots × fixed approved reference-trial panel |
| Dropout fixture/demo/experiment sizes | 50 / 400 / 4,000 enrollments |
| Screening cohort | 750 unique patients × 20 reference trial versions |
| Condition portfolio | Metabolic, cardiovascular, renal, oncology, and respiratory |
| Observation cutoff and horizon | Day 30 cutoff; synthetic dropout through day 90 |
| Synthetic dropout prevalence | Approximately 25%, documented as a generator design choice |
| Scenario analysis | Missed-dose Scenario Lab with non-causal model-sensitivity wording |
| Cohort representations | Patient-fact space and screening-profile space |
| Cohort visualization | Seeded PCA initially; DBSCAN/FAISS operate in full feature space |
| RAG corpus | Approved, versioned TrialSync eligibility criteria plus frozen synthetic fixtures |
| RAG orchestration | LangChain candidate retrieval followed by complete-criteria expansion for each bounded candidate |
| RAG generation | Gemini API structured eligibility summary with validated criterion citations |
| Provider resilience | Gemini/Groq cooldown, caching, concurrency control, bounded retry, and deterministic fallback |
| Local models | Not in the default TrialSync path |
| Delivery | GitHub Actions CI for every candidate commit; manual health-checked Compose deployment until CD is needed |
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

Complete and re-locked on 2026-07-26 after correcting R7 to the supplied LangChain/Gemini brief,
adding the trial-to-enrollment linkage required by the recruitment overview, and including
GitHub Actions CI with a documented manual deployment path. On 2026-08-01 the user approved clarification of R3's
hybrid NVIDIA/statistical generation boundary and the separate controlled-access
NCT02054715-D1 benchmark. R1 and R2 CI are complete; begin R3 only and preserve the later
phase stop points. Later phase approval does not authorize combining phases.

### Claims matrix

| Original requirement or presentation claim | TrialSync implementation or correction |
|---|---|
| Patient dropout prediction | Synthetic fixed-horizon dropout-risk demonstration; optional study-specific NCT02054715-D1 benchmark only if participant rows become accessible; no general clinical prediction claim |
| XGBoost and LightGBM | Compared with dummy and logistic baselines on the frozen synthetic dataset |
| SHAP explainability | Model contribution analysis only; never eligibility or causality |
| DBSCAN cohorts | Patient-fact and screening-profile clusters over unique synthetic patients |
| FAISS similarity | Exact cosine neighbors in versioned synthetic feature spaces |
| BioBERT matching | Deferred because no approved labelled matching task exists |
| RAG trial matching | LangChain retrieval over approved criteria plus a Gemini structured eligibility summary |
| LLM eligibility | Rejected; the deterministic engine remains authoritative |
| PDF report | Generated from canonical stored screening evidence |
| Delivery | GitHub Actions verifies the commit; manual Compose deployment applies migrations and health checks until CD is needed |
| Production clinical platform | Corrected to research-grade academic prototype using synthetic participant data |

## 7. Phase R1 — Canonical screening report PDF

### Objective

Generate a reproducible, downloadable PDF from one stored screening without asking an LLM to recreate authoritative facts.

### Report contents

- TrialSync title and educational/synthetic-data disclaimer.
- Screening ID and creation timestamp.
- Overall cautious screening state.
- Patient snapshot label, ID, version/content hash, and as-of date.
- Trial title, registry label where applicable, approved version number, and immutable version
  ID. Include a content checksum only if R1 defines and tests one from canonical stored data.
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

### Status

Complete on 2026-08-02. TrialSync now assembles a provider-free
`ScreeningReportDocument` from one owner-authorized stored screening, renders a
multi-page Unicode-safe PDF, exposes it at the authenticated `report.pdf` endpoint,
and provides a saved-screening-only **Download report** action. The report records
the immutable patient snapshot, approved trial version, engine/DSL versions, all
persisted criterion evaluations, evidence, missing information, rejected/stale
evidence, and report schema/template metadata. No migration was required.

R1 verification: focused backend report/ownership/long-text/determinism tests,
focused frontend download success/failure tests, production frontend build, full
backend/frontend verification, and desktop/narrow report-page visual review.

### R1 implementation handoff

Phase completed: R1 — Canonical screening report PDF

Outcome: Saved screenings can be downloaded as provider-free, multi-page PDFs that
agree with the browser evidence and preserve cautious result semantics.

Files changed: `backend/src/trialsync/reports/`, the screening API, frontend client/
detail page/styles/tests, pinned PDF dependencies and container fonts, README,
architecture/evaluation docs, and this phase plan.

Behavior/API/data changes: Added owner-scoped `GET /api/v1/screenings/{screening_id}/report.pdf`;
no database migration or stored-report column was added.

Tests and builds run: `make verify` (151 backend tests and 69 frontend tests at the
R1 handoff; the current repository gate reports 159 backend tests and 72 frontend
tests), migration, Ruff, mypy, evaluation, and production build; focused report
tests, backend dependency audit, and production backend image/font smoke check.

Visual states inspected: Desktop and narrow saved-screening detail pages, readable
three-page PDF metadata/evidence pages, long/Unicode pagination fixtures.

Known limitations: The R1 handoff recorded high advisories in `brace-expansion` and
`react-router`. The current audit has cleared `brace-expansion` but still reports
high React Router and moderate PostCSS advisories; they remain outside R1 and were
not auto-upgraded.

Exit criteria not yet satisfied: None for R1.

Recommended next task: Begin R3 dataset schema and seeded synthetic longitudinal generator work;
automated CD remains deferred.

## 8. Phase R2 — GitHub Actions CI (CD deferred)

### Objective

Run the repository's quality gates on pushes and pull requests. Deployment remains a documented
manual `git pull` plus health-checked Docker Compose rollout until automated CD is genuinely
needed.

### Steps

1. Add a least-privilege workflow under `.github/workflows/`.
2. Pin action major versions and document update policy.
3. Use service-container PostgreSQL or the existing Compose-compatible test path.
4. Install the pinned Python project and locked npm dependencies.
5. Run the CI gate:
   - backend formatting/lint/type checks;
   - Alembic migration verification;
   - backend unit and integration tests;
   - frontend formatting/lint/type checks;
   - frontend tests;
   - frontend production build;
   - secret scanning or the existing safe audit subset;
   - optional container builds.
6. Cache only safe dependency directories; never cache `.env`, uploads, database files, model artifacts, or MLflow stores.
7. Ensure CI requires neither a Gemini nor Groq key. Live provider evaluation remains manual
   and separately labelled.
8. Add job timeouts and concurrency cancellation for superseded branch runs.

### CI contract

CI verifies every candidate commit without deployment, provider, or database secrets. The manual
deployment procedure must be run from the exact commit that passed CI, apply migrations through
the Compose `migrate` service, and verify live/ready health before the demo is used.

### Tests

- Reproduce every workflow command locally.
- Verify migrations against an empty database.
- Verify tests use deterministic providers.
- Verify CI requires no deployment or provider secret.
- Verify a deliberate test failure fails the job during development of the workflow.
- Verify the container images build without provider credentials.

### Exit criteria

- The full repository verification gate passes in GitHub Actions.
- Backend and frontend container images build without provider credentials.
- Local and CI commands are documented.
- Workflow logs contain no secrets or synthetic document contents.
- Automated CD, protected deployment environments, and automated rollback are explicitly deferred.

### Status

Complete on 2026-08-02 for the CI scope. `.github/workflows/ci.yml` runs the repository
verification gate against PostgreSQL, audits Python dependencies, and builds both application
images without provider or deployment credentials. Automated CD is intentionally deferred; the
manual Alsomine Compose procedure remains the supported deployment path.

### Implementation handoff

Phase completed: R2 — GitHub Actions CI

Outcome: Every push, pull request, and manual workflow dispatch can run the same backend/frontend
quality gate used locally, followed by credential-free container builds.

Files changed: `.github/workflows/ci.yml`, this plan, the deployment guide, the feasibility note,
and evaluation documentation.

Behavior/API/data changes: No application, API, schema, or data behavior changed. CD and automated
rollback were not implemented.

Tests and builds run: Local `make verify`, Python dependency audit, and production Docker image
builds remain the corresponding local checks; GitHub Actions executes their clean-runner versions.

Known limitations: The workflow does not deploy to Alsomine or run browser E2E tests. Those remain
manual until a later delivery phase requires them.

Recommended next task: Begin R3 dataset schema and seeded synthetic longitudinal generator work.

## 9. Phase R3 — Synthetic longitudinal dropout protocol

### Objective

Create a reproducible event-level synthetic enrollment dataset for fixed-horizon dropout-risk
research and missed-dose scenario analysis. Use an auditable stochastic simulator as the source
of structured events and outcome labels, with optional NVIDIA NeMo Data Designer orchestration
for declared samplers, expressions, validation, and fictional narrative fields. Define a separate
NCT02054715-D1 benchmark adapter that activates only if participant rows become legitimately
accessible. Neither dataset supplies DBSCAN or FAISS data.

### 9.1 Research question

Primary:

> Within a generated clinical-trial participant cohort, can baseline and pre-cutoff operational/clinical features predict synthetic dropout before a declared follow-up horizon?

Scenario:

> How does the accepted model's output change when a plausible pre-cutoff dose event is changed
> from administered to missed, with every dependent feature recomputed?

External benchmark, conditional on access:

> Within the NCT02054715-D1 study population and its published follow-up definition, do baseline
> variables provide reproducible held-out signal for the study's recorded dropout outcome?

This external question is deliberately narrower than the synthetic multi-condition question. Its
feature schema, follow-up semantics, splits, metrics, model artifacts, and claims remain separate.

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
- Immutable TrialSync patient snapshot ID.
- Approved trial version ID.
- Canonical screening ID and stored eligibility state for that exact snapshot × trial version.
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

Each `research_enrollment` is the explicit versioned bridge between the dropout dataset and the
matching product. It references one immutable patient snapshot, one approved trial version, and
the ordinary screening created by the exact single-screening service for that pair. Longitudinal
events are generated only for linked screenings whose stored state is `potentially_eligible`, so
the dataset represents simulated enrolled participants without relabelling screening rows as
dropout outcomes.

### 9.4 Two-track data strategy

#### Track A — required public synthetic protocol

Track A is the only dataset required to build, test, run, and demonstrate TrialSync. Use a hybrid
pipeline:

1. TrialSync code owns relational IDs, chronology, eligibility linkage, event schedules, hidden
   hazard coefficients, stochastic outcome sampling, censoring, splits, and checksums.
2. NeMo Data Designer may declaratively orchestrate statistical samplers, dependent expressions,
   schema validation, and optional fictional text. The evaluated configuration and provider/model
   metadata are versioned when used.
3. An LLM must not directly choose dropout labels, fabricate model ground truth, or see hidden
   generator state. Optional generated text is excluded from R4 features unless a later reviewed
   protocol defines and leakage-tests it.
4. The generator must run in an offline deterministic mode without an NVIDIA account. NVIDIA is
   an optional research accelerator, not a runtime or clean-reproduction dependency.

NVIDIA's current Data Designer documentation describes schema-driven samplers, expressions,
structured generation, validation, previews, and provider-backed execution:
[NeMo Data Designer](https://docs.nvidia.com/nemo/datadesigner/getting-started/welcome).

#### Track B — optional future external benchmark

NCT02054715-D1's public dictionary contains a scrambled participant ID, baseline variables,
`Dropouttime`, and `Dropout` reason, and the public paper reports aggregate study results. These
assets are enough to define an adapter and an explicitly synthetic, NCT-inspired fixture, but not
to train or evaluate a model on real participants. NCI now directs NCTN/NCORP patient-level access
through dbGaP, and NCT02054715 is not in NCI's current available-dataset list as of 2026-08-01.
Therefore Track B is a future adapter, not a currently runnable real-data benchmark. If participant
rows later become available from a legitimate source:

1. Record the accession or delivery source, applicable use terms, storage boundary, and any
   expiration date.
2. Inspect row count, event count, missingness, follow-up timing, censoring semantics, and permitted
   uses before freezing a study-specific task.
3. Keep all governed rows, fitted artifacts, intermediate files, logs, and credentials outside
   Git and outside the public TrialSync deployment.
4. Do not send rows or row-derived prompts to NVIDIA, Gemini, Groq, or another hosted provider
   unless the source terms permit that processing.
5. Do not merge Track B participants with Track A, use them to populate the public demo, or claim
   that one oncology psychoeducation study validates multi-condition day-30/day-90 prediction.
6. Treat any synthetic rows fitted from Track B as governed derivatives until the applicable
   terms and disclosure review say otherwise. More generated rows do not create more independent
   real-world evidence.

Track B may evaluate the same model families, but it receives its own feature contract, split,
MLflow experiment, report, and claim label. Until participant rows are accessible, Track B remains
a documented future-validation adapter and Track A remains complete on its own.

Primary sources: [NCT02054715-D1 data dictionary](https://nctn-data-archive.nci.nih.gov/system/files/dataset/NCT02054715-D1/NCT02054715-D1-Data-Dictionary.pdf),
[published study](https://pubmed.ncbi.nlm.nih.gov/30291797/),
[NCI NCTN/NCORP Data Archive](https://dctd.cancer.gov/research/networks/nctn/data-archive), and
[NIH dbGaP access process](https://www.grants.nih.gov/policy-and-compliance/policy-topics/sharing-policies/accessing-data/dbgap).

### 9.5 Generation principles

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
11. Generate the matching patient/trial inputs first, call the existing single-screening service,
    and freeze the linkage before generating any longitudinal events or dropout outcome.
12. Use documented bounded resampling to reach the requested enrollment count when a generated
    snapshot is not potentially eligible; report attempted-versus-accepted counts and never use a
    future dropout outcome during acceptance.
13. Freeze generator configuration before model tuning and record whether each field came from
    TrialSync code, a statistical sampler, an expression, or an optional LLM-backed column.
14. Validate generated distributions and conditional relationships against declared assumptions;
    do not describe resemblance to real NCT02054715-D1 participants unless a row-level Track B
    analysis measured it.

### 9.6 Dataset sizes

Use three locked sizes:

- Tiny fixture: 50 enrollments for unit and schema tests.
- Demo cohort: 400 enrollments for the Scenario Lab and local inference.
- Experiment cohort: 4,000 enrollments for model comparison and stress evaluation.

The 400-enrollment demo cohort is the bounded product-facing cohort whose enrollment links are
materialized for R5. The 4,000-enrollment experiment cohort remains an offline versioned research
artifact; its linkage manifest is used for reproducibility and training, not bulk ordinary
screening history.

Target approximately 25% synthetic dropout through day 90. Report the exact generated
prevalence and event counts for every split; never adjust the test set after inspection.

### 9.7 Split strategy

- Split by participant.
- Fit preprocessing on training data only.
- Prefer a generator-time or site-based holdout in addition to a random stratified split.
- Include a stress-test regime with changed coefficients or missingness.
- Freeze the primary test split before model tuning.
- Use repeated seeds or cross-validation only on training/validation data.

### 9.8 Artifacts and documentation

- Versioned dataset schema.
- Generator configuration.
- Field-level provenance identifying deterministic, statistical, expression-derived, and optional
  LLM-generated columns.
- NVIDIA Data Designer recipe, dependency/provider versions, token/cost summary, and validation
  report when the optional path is used; never credentials or restricted prompts.
- Feature dictionary.
- Outcome definition.
- Leakage audit.
- Data-quality report.
- Aggregate distributions and missingness report.
- Generator unit tests.
- Dataset card describing intended and prohibited uses.
- A Track B access/governance record and separate benchmark protocol, or an explicit
  `not available` decision with no implied validation claim.

### Tests

- Same seed produces identical checksums.
- Different seed changes participant values.
- IDs are unique and fictional.
- Dates follow the declared ordering.
- No post-cutoff feature leakage.
- Dropout labels agree with event times.
- Every enrollment resolves to exactly one immutable patient snapshot, approved trial version,
  and `potentially_eligible` canonical screening.
- Linkage metadata cannot change when risk predictions are regenerated.
- Censoring is internally consistent.
- Values and units stay in declared artificial ranges.
- Train/validation/test participants do not overlap.
- Hidden generator labels are excluded from exported model features.
- Missed-dose scenario edits recompute every dependent adherence feature.
- Offline generation succeeds without NVIDIA credentials.
- Optional Data Designer output conforms to the same schema and invariant checks as offline output.
- No LLM-generated field directly or indirectly determines the label.
- Repository and public-demo scans contain no Track B rows, governed derivatives, access tokens,
  or fitted restricted-data artifacts.

### Exit criteria

- The dataset card and feature dictionary are understandable without reading generator code.
- Leakage tests pass.
- Outcome prevalence and split event counts are reported.
- The dataset card reports enrollments and dropout prevalence by linked trial version.
- The report names which columns, if any, used NeMo Data Designer and demonstrates that the label
  and split remained simulator-owned.
- Track B is either backed by a recorded legitimate row-level source and separate protocol or
  clearly marked unavailable; synthetic generation does not masquerade as external validation.
- The user approves the artificial assumptions before model training begins.

### Stop point

Pause for review of the generated dataset report before implementing model experiments.

## 10. Phase R4 — Dropout model experiments, MLflow, and SHAP

### Objective

Build a reproducible offline research pipeline comparing interpretable and tree-based classifiers
on the approved Track A synthetic dataset. If Track B participant rows become accessible, run a separate
study-specific benchmark without merging its participants, features, metrics, or artifacts into
Track A.

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
- Track A and Track B use distinct feature builders, experiment names, model aliases, artifact
  locations, and intended-use labels.

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
- Tags describing the data track, study scope, and intended/prohibited uses.
- A data-track tag (`synthetic_multicondition` or `controlled_nct02054715_d1`) and, for Track B,
  non-sensitive approval/protocol metadata without governed row content.

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

For Track A, acceptance must focus on pipeline correctness and reproducibility rather than
impressive synthetic scores. Track B, when available, additionally tests study-specific held-out
performance but still cannot establish clinical validity or broad generalization:

- Training is reproducible within documented tolerance.
- The final model beats the dummy baseline on the frozen synthetic test set.
- Calibration is reported and not hidden.
- Inference schema validation is strict.
- SHAP contributions reconcile with the model output within library tolerance.
- A simple logistic baseline remains visible beside the tree model.
- Known generator signal recovery is discussed without claiming real-world validity.
- No Track B model can become the champion for the multi-condition Scenario Lab, and no Track A
  model can be reported as externally validated.

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

- `research_enrollment_links`
  - owner;
  - R3 research enrollment ID;
  - immutable patient snapshot ID;
  - approved trial version ID;
  - canonical screening ID;
  - dataset/linkage version and checksum;
  - unique constraints on the enrollment and exact snapshot × trial-version context.
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
  - research enrollment link ID;
  - model version;
  - feature snapshot JSON/hash;
  - probability;
  - thresholded research label;
  - top SHAP contributions;
  - prediction timestamp;
  - synthetic/research disclaimer version.

The enrollment-link record provides the immutable join to its patient snapshot, approved trial
version, and canonical screening. Do not attach mutable risk fields to `screenings` or `patients`.

### API

Candidate routes:

```text
GET  /api/v1/research/risk/models
GET  /api/v1/research/risk/models/{model_version}
POST /api/v1/research/risk/predictions
GET  /api/v1/research/risk/predictions
GET  /api/v1/research/risk/predictions/{prediction_id}
GET  /api/v1/research/trial-overview
GET  /api/v1/research/trial-overview/{trial_version_id}
```

The overview endpoints group ordinary screening states by approved trial version. Their retention
distribution includes only potentially eligible screenings with a version-matched
`research_enrollment` and prediction, and returns explicit linked/unlinked counts so the graph's
denominator is visible. One aggregate uses one approved model version, horizon, and versioned band
policy; predictions from different model versions are never mixed into the same chart.

Example overview fields:

```json
{
  "trial_version_id": "trial-version-id",
  "screening_counts": {
    "potentially_eligible": 28,
    "needs_review": 9,
    "likely_ineligible": 13
  },
  "retention": {
    "eligible_total": 28,
    "linked_predictions": 20,
    "unlinked_eligible": 8,
    "risk_bands": {
      "lower": 11,
      "near_threshold": 4,
      "higher": 5
    },
    "model_version": "dropout-lightgbm:1",
    "horizon_day": 90,
    "band_policy_version": "1"
  }
}
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
- Derive chart bands from the accepted model's versioned threshold/band policy.
- Do not call Gemini or Groq.
- Do not trigger screening.
- Do not convert probability into `potentially_eligible`, `likely_ineligible`, or `needs_review`.
- Do not permit prediction creation for arbitrary real records.
- Resolve trial-overview risk aggregates only through the immutable research-enrollment linkage.

### Frontend

Create a clearly labelled research area:

- Research overview with synthetic-data boundary.
- Model card with dataset, horizon, metrics, threshold, and limitations.
- Synthetic participant selector or form.
- Risk result with probability, threshold, and top SHAP contributions.
- Trial Recruitment Overview with a trial selector, total screening-state counts, and a compact
  chart of linked potentially eligible participants by dropout-risk band.
- Visible numerator/denominator labels showing how many potentially eligible screenings have a
  linked research enrollment and prediction.
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
- Trial grouping uses approved trial-version IDs rather than mutable trial titles.
- Overview state counts agree with ordinary saved screenings.
- Risk-band counts include only version-matched linked enrollments and expose unlinked counts.
- Overview aggregates reject mixed model, horizon, or band-policy versions.
- No cross-owner or cross-version linkage.
- Provider/network-disabled behavior.
- UI loading, populated, invalid-input, artifact-missing, and API-error states.

### Visual review

- Research overview.
- Trial Recruitment Overview with no screenings, mixed eligibility states, no linked predictions,
  partial linkage, all risk bands, long trial names, and narrow layout.
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
- Every trial-overview risk count is traceable to a versioned enrollment, screening, and prediction.
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

## 13. Phase R7 — Eligibility-criteria RAG with LangChain and Gemini

### Objective

Implement the RAG component from the project brief: a coordinator uploads or selects a patient
record, LangChain retrieves the most relevant eligibility criteria from TrialSync's approved trial
corpus, and Gemini generates a structured eligibility summary grounded only in those criteria.

### Corpus

Build the retrieval corpus from approved, immutable TrialSync trial versions. Each indexed chunk
must retain the trial version ID, criterion ID, criterion kind, source text, content checksum, and
index version. A checked-in synthetic fixture corpus supports deterministic tests and the final
demonstration. No live external trial registry is required.

### Retrieval sequence

```text
Coordinator uploads or selects a patient record
  -> review/approve extracted patient facts
  -> LangChain retrieves top candidate trial versions from approved criterion chunks
  -> expand each bounded candidate to its complete ordered approved criteria set
  -> Gemini generates a schema-validated eligibility summary from the complete candidate context
  -> validate every trial-version and criterion citation
  -> coordinator opens a candidate trial match
  -> existing deterministic screening verifies the final eligibility state
  -> canonical screening result and PDF report
```

### LangChain retrieval

- Use LangChain as the required retrieval orchestration layer.
- Begin with a reproducible lexical or locally computed embedding retriever over approved criteria.
- Keep chunking, preprocessing, top-k, and index versions explicit.
- Use first-stage criterion retrieval to rank candidate trial versions.
- For each bounded top candidate, load its complete ordered approved criteria set before
  generation; a low-scoring or lexically unrelated exclusion criterion must not be omitted.
- If a complete candidate does not fit the declared context bound, reduce the number of candidate
  trials or summarize candidates separately—never truncate a trial's required criteria silently.
- Measure retrieval independently from Gemini generation.
- Do not reuse the R6 participant-similarity FAISS index automatically; patient similarity and
  eligibility-criteria retrieval are different tasks and require separate indexes.

### Storage

Candidate entities:

- `eligibility_rag_indexes`
  - corpus checksum;
  - chunking/retriever/index versions;
  - build timestamp.
- `eligibility_rag_runs`
  - owner;
  - patient snapshot;
  - index and prompt versions;
  - timestamps and status.
- `eligibility_rag_results`
  - run;
  - trial version and criterion;
  - rank and retrieval score;
  - Gemini structured-summary fields and validated citations.

### API

Candidate routes:

```text
POST /api/v1/eligibility-rag/match
GET  /api/v1/eligibility-rag/runs/{run_id}
POST /api/v1/eligibility-rag/runs/{run_id}/screen/{trial_version_id}
```

The final route invokes the existing single-screening operation for the selected patient snapshot
and approved trial version; it does not let Gemini create or alter the screening result.

### Gemini structured-summary contract

Gemini receives only the approved patient summary and complete approved criterion sets for the
bounded candidate trial versions identified by LangChain. Its response must validate against a
versioned schema containing:

- candidate trial version;
- concise eligibility summary;
- matched, conflicting, and missing-information items;
- cited TrialSync criterion IDs for every substantive item;
- retrieval, model, and prompt-version metadata.

The generated summary is the RAG presentation layer. The deterministic screening engine remains
the final criterion evaluator, allowing the project to demonstrate both modern RAG and a
reproducible patient-matching result.

### Provider resilience

1. Bound the patient context, retrieved chunks, output schema, request time, and retry budget.
2. Parse provider rate-limit responses and maintain a short in-process cooldown.
3. Limit concurrent Gemini requests.
4. Cache only safe outputs by patient snapshot checksum, corpus/index, retriever, model, and
   prompt versions within the owning workspace.
5. Preserve ranked LangChain retrieval results when Gemini is unavailable or returns invalid data.
6. Keep the existing Groq extraction and explanation paths independent from the Gemini RAG path.

### Configuration

Add explicit settings for:

- `TRIALSYNC_ELIGIBILITY_RAG_PROVIDER=gemini|disabled`;
- `GEMINI_API_KEY`;
- `TRIALSYNC_GEMINI_MODEL`;
- retrieval top-k and maximum candidate-trial count;
- Gemini request timeout, output bound, concurrency, and retry budget.

Provider keys remain optional for local/core operation, are never required by automated tests, and
enter production only through the protected GitHub environment.

### Retrieval and grounding evaluation

Create a frozen patient-query fixture set with expected relevant trials and criteria. Report:

- Recall@k and mean reciprocal rank for trial retrieval.
- Criterion Recall@k.
- Complete-criteria expansion coverage of 100% for every generated candidate summary.
- Retrieval determinism for the frozen corpus.
- Structured-output schema validity.
- Criterion-citation validity and grounded-claim precision.
- Unsupported-claim count.
- No-results, provider-failure, and prompt-injection behavior.

### Tests

- Approved-version-only corpus construction and owner scoping.
- Stable criterion chunk IDs, checksums, and index versions.
- Retrieval determinism and top-k bounds.
- Correct grouping by trial version.
- Complete ordered criteria expansion after candidate retrieval.
- Oversized candidate handling never silently drops a required criterion.
- Valid, missing, and fabricated Gemini criterion citations.
- Invalid-schema, timeout, rate-limit, and provider-disabled states.
- Ranked retrieval remains available without Gemini.
- The selected match calls the unchanged single-screening service.
- Generated text cannot alter criterion or overall eligibility results.

### Frontend

- Patient-record upload or existing-patient selector.
- Ranked candidate trials with matched eligibility criteria and retrieval scores.
- Structured Gemini eligibility summary with links to the cited criteria.
- Clear matched, conflicting, and missing-information sections.
- Action to run the authoritative screening for a selected trial.
- Link from the completed result to the eligibility-report PDF.
- Loading, no-match, invalid-summary, provider-unavailable, long-text, and narrow states.

### Visual review

- Uploaded-record and existing-patient flows.
- Populated, no-match, invalid-summary, provider-unavailable, long-criteria, and narrow states.
- Criterion citation navigation, keyboard focus, contrast, and reduced motion.

### Exit criteria

- LangChain performs a distinct, measured retrieval step over approved trial criteria.
- Every candidate passed to Gemini contains its complete approved criteria set.
- Gemini produces the required schema-validated summary using only the expanded candidate context.
- Every substantive generated item has a valid TrialSync criterion citation.
- A selected candidate runs through the existing deterministic screening engine.
- Retrieval remains usable when Gemini is unavailable.
- The workflow ends in the canonical browser result and downloadable PDF.

## 14. Phase R8 — Integrated evaluation and final delivery

### Objective

Demonstrate the extension coherently, reproduce it from a clean environment, and align every presentation claim with evidence.

### Required evaluation package

1. Core deterministic screening regression results.
2. Canonical PDF consistency checks.
3. CI workflow evidence.
4. Synthetic dataset card and leakage audit.
5. Generator provenance and NeMo Data Designer comparison/validation evidence when that optional
   path is used.
6. Dropout model comparison:
   - dummy;
   - logistic regression;
   - XGBoost;
   - LightGBM.
7. Calibration and selected threshold.
8. MLflow run/registry evidence.
9. SHAP global and local explanation examples.
10. Track B access decision and, only when approved and executed, a separately labelled
    NCT02054715-D1 benchmark report.
11. Trial Recruitment Overview reconciliation of screening totals, linked enrollments, predictions,
   risk bands, and visible denominators.
12. Patient-fact and screening-profile DBSCAN parameter/stability reports.
13. Both FAISS exact-neighbor verifications and Cohort Atlas projection evidence.
14. LangChain criteria-retrieval, complete-criteria expansion, and Gemini grounded-generation metrics.
15. Gemini/Groq cooldown, cache, retry, and degraded-mode behavior.
16. GitHub Actions CI evidence plus the manual deployed-commit and health-check record; automated
    CD/rollback evidence only if that later scope is enabled.
17. Security, dependency, restricted-data, and secret checks.

### Final demonstration script

1. Open the seeded synthetic workspace.
2. Show a patient snapshot and approved trial version.
3. Run or open a deterministic screening.
4. Explain one pass, fail, and unknown criterion from stored evidence.
5. Download the canonical PDF and show that it matches the result page.
6. Open the research area and state the synthetic-data boundary.
7. Show the approved dropout model card and comparison with the logistic baseline.
8. Run one synthetic dropout-risk prediction.
9. Open the Trial Recruitment Overview, select one trial, and compare its canonical screening
   counts with the linked dropout-risk distribution.
10. Explain the top SHAP contributions without causal language.
11. Switch the Cohort Atlas between patient-fact and screening-profile views, show noise
    handling, and inspect one FAISS neighbor comparison.
12. Upload a patient record, retrieve relevant trial criteria with LangChain, show the
    citation-validated Gemini summary, and run the selected deterministic screening.
13. Show that neither risk, cluster, similarity, retrieval, nor LLM output changes eligibility.
14. Show CI evidence, the manually deployed commit, the production health gate, and the offline fallback.

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
- GitHub Actions CI success plus manual deployment and health-gate evidence. Automated CD and
  rollback are deferred unless the project later needs them.
- Dependency and secret audit.
- No generated research artifact or restricted data accidentally tracked.
- No local language model is required by the clean setup or live demonstration.

### Exit criteria

- Every approved phase has reproducible evidence.
- Core matching works without Gemini or Groq; LangChain retrieval remains available without generation.
- Core screening remains deterministic and unchanged.
- Research outputs are clearly synthetic and versioned.
- No final claim exceeds the implemented evaluation.

## 15. Cross-phase database and migration rules

- Add one Alembic revision per bounded schema phase.
- Research migrations must not rewrite immutable screening history.
- Research enrollment links reference immutable snapshots, approved trial versions, and canonical
  screenings through foreign keys plus a linkage checksum; they are append-only and cannot be
  repointed when a model or prediction changes.
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

- call Gemini or Groq;
- depend on a live external trial registry;
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
- NVIDIA NeMo Data Designer only if R3 demonstrates a concrete benefit over the offline
  simulator and its license, Python 3.12 support, dependency weight, provider costs, and
  credential-free fallback are accepted.
- scikit-learn.
- XGBoost.
- LightGBM.
- MLflow.
- SHAP.
- FAISS CPU.
- LangChain for the required eligibility-criteria retrieval pipeline.
- A Gemini API client or the LangChain Gemini integration.
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
ci: add repository verification workflow
feat: add reproducible hybrid synthetic participant generator
feat: add dropout model experiments and MLflow tracking
feat: add versioned synthetic risk inference
feat: add research cohort and similarity explorer
feat: add LangChain and Gemini eligibility-criteria RAG
test: complete research extension evaluation
docs: finalize research report and presentation
```

Commits are phase checkpoints, not permission to combine several phases into one implementation pass.

## 20. Final scope audit

- [x] R1–R8 remain separate bounded phases.
- [x] BioBERT, restricted-data dependencies, and local-LLM fallback are deferred.
- [x] Dropout and cohort/similarity use different datasets and units of analysis.
- [x] The public dropout label and split remain owned by the audited simulator; NeMo Data Designer
  is optional orchestration with a credential-free fallback.
- [x] NCT02054715-D1 is a future, separate study-specific adapter and never inflates the public
  synthetic cohort or its real-world evidence claim.
- [x] Dummy, logistic, XGBoost, and LightGBM are compared before champion selection.
- [x] MLflow uses a private optional Compose profile.
- [x] Research analytics appear in labelled main navigation.
- [x] Dropout uses day 30 → day 90 over 50/400/4,000 synthetic enrollments.
- [x] Cohort analysis uses 750 unique patients × 20 fixed reference trials.
- [x] The Scenario Lab presents model sensitivity, never causality.
- [x] The Cohort Atlas supports patient-fact and screening-profile representations.
- [x] Eligibility RAG uses LangChain candidate retrieval, complete-criteria expansion, and Gemini structured summaries.
- [x] Gemini/Groq rate-limit handling uses cooldown/cache/concurrency/fallback instead of local models.
- [x] GitHub Actions CI verifies the tested repository without provider or deployment secrets.
- [ ] Automated CD, protected deployment, and rollback are deferred until the deployment target
  and release frequency justify them.
- [x] Trial-grouped risk counts resolve through versioned research-enrollment linkages.
- [x] Every research output remains separate from deterministic eligibility.

## 21. Phase status tracker

| Phase | Status | Approval evidence | Exit evidence |
|---|---|---|---|
| R0. Scope lock | Complete | Revised scope re-locked by user after final consistency audit, 2026-07-26 | This document |
| R1. Canonical report PDF | Complete | User selected evidence-backed reporting, 2026-07-26 | Provider-free typed report assembler, owner-scoped PDF endpoint, complete evidence/missing-information/stale-evidence/ownership/long-text/determinism tests, frontend download states, production build, and visual review, 2026-08-02 |
| R2. GitHub Actions CI (CD deferred) | Complete | User selected CI-only delivery for the controlled project, 2026-08-02 | Credential-free GitHub Actions verification, Python audit, and backend/frontend container builds; manual Compose deployment remains documented |
| R3. Synthetic dropout protocol/dataset | Approved | User selected dropout-risk modeling on 2026-07-26 and clarified hybrid NVIDIA generation plus separate NCT02054715-D1 validation on 2026-08-01 | |
| R4. Dropout models/MLflow/SHAP | Approved | User selected dropout-risk modeling, 2026-07-26 | |
| R5. Research-risk API/UI | Approved | User selected research delivery surface, 2026-07-26 | |
| R6. Screening-derived DBSCAN/FAISS cohorts | Approved | User selected cohort analytics, 2026-07-26 | |
| R7. LangChain/Gemini eligibility RAG | Approved | Corrected to the supplied project brief, 2026-07-26 | |
| R8. Evaluation/final delivery | Approved | User selected supporting engineering/evaluation, 2026-07-26 | |

Allowed statuses: `Awaiting review`, `Approved`, `Revise`, `Not authorized`, `In progress`, `Blocked`, `Complete`, `Skipped`, or `Deferred`.

R1 and R2 are complete. Begin R3 only and preserve every later stop point.

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
