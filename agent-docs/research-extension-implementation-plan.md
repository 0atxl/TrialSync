# TrialSync Research Extension: Phased Implementation Plan

**Date:** 2026-07-24
**Status:** R0 was revised and re-locked on 2026-07-26. R1 completed on 2026-08-02, and
R2 CI completed on 2026-08-02; automated CD remains deferred. R3 is complete and accepted:
the 20-enrollment smoke, 400-enrollment demo, and 4,000-enrollment experiment artifacts pass the
declared schema, linkage, chronology, censoring, split, and leakage checks. R4's manual Kaggle
experiment completed on 2026-08-15 with dummy, logistic-regression, XGBoost, and LightGBM
comparisons, bootstrap uncertainty, SHAP explanations, and a local MLflow model record. The
original frozen validation rule selected LightGBM; historical XGBoost (`xgboost-05`) was the
initial user-selected R5 runtime/product model based on the reviewed comparison. Neither XGBoost
version is described as validation-selected. The committed R4 experiment report records the selection,
metrics, uncertainty, SHAP, reproducibility metadata, and R5 handoff.
The later separately reviewed controlled-synthetic v2 bundle supplies the active runtime model
`dropout-xgboost-06-v1` (`xgboost-06`), feature contract `r4-day30-features-v2`, threshold `0.445`,
and day-90 horizon. `xgboost-06` was not part of the original R4 comparison and was reviewed and
user-selected for directional realism. Its metrics remain limited to that controlled synthetic task and are
not clinical or real-world validation.
The user approved R5A, a product-wide frontend experience redesign, on 2026-08-25. R5A follows the
implemented R5/R6 integration and is the next implementation gate before R7.
**Relationship to the current application:** Incremental extension after the completed deterministic TrialSync workflow. This plan does not replace the existing architecture or reopen completed rebuild phases.

## 1. Purpose

This document is the authoritative implementation sequence for **TrialSync: Clinical Trial
Patient Matching and Dropout Prediction**. It evolves the completed explainable matching product
into a broader, testable clinical-research platform while preserving deterministic eligibility as
the trusted matching core.

The approved extension contains:

1. Canonical evidence-backed PDF reporting and GitHub Actions CI, with automated CD deferred.
2. A separate, auditable longitudinal enrollment generator for dropout-risk research, using
   NVIDIA NeMo Data Designer and a future external benchmark adapter if
   suitable row-level data becomes legitimately accessible.
3. Logistic regression, XGBoost, LightGBM, MLflow, SHAP, and a missed-dose Scenario Lab.
4. A screening-derived patient cohort for DBSCAN clustering, FAISS similarity, and the
   Cohort Atlas.
5. A product-wide R5A frontend experience redesign covering ingestion, core records, dashboard,
   dropout workflow, and interactive Cohort Atlas.
6. LangChain retrieval over approved, versioned trial eligibility criteria with a
   Gemini-generated structured eligibility summary and citation validation.
7. Integrated evaluation, documentation, and presentation evidence.

The accepted contracts, reports, source, and tests record the current feasibility and rationale.

The extension has two distinct surfaces:

```text
TrialSync patient-matching core
  -> reviewed patient/trial inputs
  -> deterministic pass/fail/unknown screening
  -> canonical evidence and downloadable report

TrialSync research analytics
  -> NeMo-backed synthetic longitudinal enrollment dataset
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
- R3 is accepted and complete. Its generator, schema contract, smoke/demo/experiment artifacts,
  EDA, dataset card, feature dictionary, linkage manifest, leakage audit, and checksums are frozen.
- R4's offline experiment and repository-facing report are complete. The historical LightGBM
  validation selection, XGBoost comparison, bootstrap intervals, SHAP artifacts, and MLflow record
  are documented; R5 packages the user-selected XGBoost runtime artifact without retraining.
- R5 packaging, inference, and API foundations exist, but their uncommitted training-row linkage
  must be replaced by the approved platform enrollment/event/follow-up contract before frontend
  integration.
- R6's sealed reference cohort, DBSCAN reports, exact FAISS indexes, and artifact read APIs exist,
  but saved-screening projection and out-of-sample query bridges remain.
- No integrated research-tools UI yet; dropout, cohort context, and similarity must be independently
  selectable from a saved screening.
- No LangChain eligibility-criteria retriever, Gemini structured-summary provider, or RAG evaluation.
- No research-extension evaluation/reporting package.

## 3. Fixed decisions

These decisions apply to every phase unless the user explicitly changes them after reviewing this document.

### 3.1 Data boundary

- The repository, automated tests, demo, Groq requests, screenshots, and downloadable reports use fictional synthetic participant data only.
- The public, versioned and auditable longitudinal dropout dataset is generated specifically for
  this project with NVIDIA NeMo Data Designer and documented generation assumptions. Exact
  configuration and frozen run artifacts are preserved; byte-identical regeneration is not
  claimed without a project-level sampler seed.
- NVIDIA NeMo Data Designer is the selected generation tool for approved samplers, expressions,
  validation, and optional fictional narrative fields. A reviewed random sampler draw and dependent
  expression define the synthetic dropout label; NeMo is not an authority for eligibility or real-world clinical
  ground truth, and TrialSync still owns dataset splits and evaluation boundaries.
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

- Dropout-risk prediction is entered from the existing saved-screening workspace through a
  visibly labelled research panel. Aggregate cohort and trial-level analytics may use dedicated
  research pages, but prediction is not presented as a disconnected product feature.
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
- A separate, versioned research-risk API integrated into the existing screening UI.
- A trial-centric recruitment and retention overview, including grouped screening counts and an aggregate dropout-risk chart for explicitly linked research participants.
- DBSCAN cohort discovery and FAISS participant similarity.
- The R5A frontend experience redesign defined in
  [`r5a-frontend-experience-redesign-plan.md`](r5a-frontend-experience-redesign-plan.md).
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
 |     -> R4 Dropout model experiments
 |           -> R5 Versioned risk API and Scenario Lab --+
 |                                                        |
 +--> R6 Screening-derived cohorts, DBSCAN, FAISS --------+--> R5A Frontend experience redesign
                                                               -> R7 Eligibility-criteria RAG
 |
 +--> R8 Integrated evaluation, documentation, and presentation
```

R1 and R2 may proceed independently after R0. R4 depends on the accepted R3 longitudinal
dropout dataset, and R5 depends on an R4 model passing its declared acceptance criteria. R6
uses a different screening-derived patient cohort and does not depend on the dropout dataset.
R7 is independent of both research datasets and uses the existing approved trial versions as
its retrieval corpus, but implementation is intentionally sequenced after R5A so its frontend is
built into the accepted information architecture rather than the superseded interface.

### Current implementation order

The R5/R6 backend and initial frontend integration are implemented. The next implementation phase is
R5A, executed through the preflight and seven reviewable implementation stages defined in the
dedicated R5A plan. R7 remains approved but does not start until the redesigned frontend is
accepted, preventing new RAG work from being built into an interface scheduled for replacement.

## 6. Phase R0 — Scope lock and research protocol

### Objective

Record the approved extension boundaries and prevent later phases from silently expanding them.

### Locked decisions

| Decision | Approved choice |
|---|---|
| Model comparison | Dummy, logistic regression, XGBoost, and LightGBM; package user-selected XGBoost for R5 runtime |
| MLflow | Private, local SQLite-backed tracking through an optional Compose profile |
| Research navigation | Visible, clearly labelled main-navigation area |
| Dropout data | NVIDIA NeMo Data Designer-backed multi-condition longitudinal synthetic dataset with explicit TrialSync validation and outcome definitions |
| External dropout benchmark | NCT02054715-D1 public schema now; row-level evaluation only if the participant data becomes legitimately accessible, with separate artifacts and claims |
| Cohort data | Unique synthetic patient snapshots × fixed approved reference-trial panel |
| Dropout fixture/demo/experiment sizes | 50 / 400 / 4,000 enrollments |
| Screening cohort | 750 unique patients × 20 reference trial versions |
| Condition portfolio | Metabolic, cardiovascular, renal, oncology, and respiratory |
| Observation cutoff and horizon | Day 30 cutoff; synthetic dropout through day 90 |
| Synthetic dropout prevalence | Emergent from frozen 8%/18%/35%/55% hidden-tier probabilities; report every run, never force an exact rate |
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
NeMo-sampler/TrialSync-shaping boundary and the separate controlled-access
NCT02054715-D1 benchmark. R1 and R2 CI are complete; continue R3 only and preserve the later
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
R1 handoff; the current repository gate reports 172 backend tests and 72 frontend
tests), migration, Ruff, mypy, evaluation, and production build; focused report
tests, backend dependency audit, and production backend image/font smoke check.

Visual states inspected: Desktop and narrow saved-screening detail pages, readable
three-page PDF metadata/evidence pages, long/Unicode pagination fixtures.

Known limitations at the R1 handoff: dependency audits reported `brace-expansion`, React Router,
and PostCSS findings. Subsequent lockfile remediation cleared those findings; the current npm audit
reports zero vulnerabilities. The remaining Python `cryptography` exception belongs to the offline
Data Designer dependency and is documented separately.

Exit criteria not yet satisfied: None for R1.

Recommended next task at R1 completion: Begin R3 dataset schema and versioned NeMo-backed
longitudinal generator work;
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

Recommended next task at R2 completion: Begin R3 dataset schema and versioned NeMo-backed
longitudinal generator work.

## 9. Phase R3 — Synthetic longitudinal dropout protocol

### Objective

Create a versioned, auditable event-level synthetic enrollment dataset for fixed-horizon dropout-risk
research and missed-dose scenario analysis using NVIDIA NeMo Data Designer for the generation
workflow and explicit TrialSync validation/outcome definitions. Define a separate
NCT02054715-D1 benchmark adapter that activates only if participant rows become legitimately
accessible. Neither dataset supplies DBSCAN or FAISS data.

### 9.1 Research question

Primary:

> Within a generated clinical-trial participant cohort, can baseline and pre-cutoff operational/clinical features predict synthetic dropout before a declared follow-up horizon?

Scenario:

> How does the configured runtime model's output change when a plausible pre-cutoff dose event is changed
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

- `dropout_by_day90`, defined as dropout during days 31–90 after the day-30 feature cutoff.
- `dropout_day`.
- `dropout_reason` from a declared synthetic taxonomy.
- `event_observed` and `censor_day` under the frozen follow-up rule.

Required event tables:

- `research_participants`;
- `research_enrollments`;
- `research_dose_events`;
- `research_visit_events`;
- `research_measurements`;
- `research_adverse_events`;
- `research_outcomes`.

Each `research_enrollment` is the explicit versioned bridge contract between the dropout dataset
and the matching product. During offline R3 generation it carries synthetic snapshot, trial-version,
and screening identifiers and records the result of the pure canonical domain engine; it does not
claim that corresponding PostgreSQL rows already exist. R5 may materialize the bounded 400-row
demo linkage through the ordinary service layer. Longitudinal events are generated only for rows
whose canonical domain result is `potentially_eligible`, without relabelling screening state as a
dropout outcome.

### 9.4 Two-track data strategy

#### Track A — required public synthetic protocol

Track A is the only dataset required to build, test, run, and demonstrate TrialSync. Use the
NeMo-backed pipeline:

1. TrialSync code owns relational IDs, chronology, eligibility linkage, event schedules, censoring,
   participant-level splits, and leakage-safe derived views.
2. Data Designer generates the reviewed synthetic participant, enrollment, event, and outcome
   fields through statistical samplers and seed-aware dependent expressions. The evaluated
   configuration, package version, execution summary, and provenance metadata are versioned.
3. The sampler-and-expression configuration—not an LLM narrative—defines the dropout label. Optional fictional
   text is excluded from R4 features unless a later reviewed protocol defines and leakage-tests it.
4. The reviewed R3 workflow records its local execution/model-usage summary and generation
   metadata. An offline Python simulator is not part of the current approved R3 implementation.

NVIDIA's current Data Designer documentation describes schema-driven samplers, expressions,
structured generation, validation, previews, and optional provider-backed columns. The current R3
recipe uses only local sampler/expression execution:
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

1. Preserve the exact Data Designer configuration and run artifacts. Data Designer 0.8 does not
   expose the project-level sampler seed required for a byte-identical rerun, so do not claim
   checksum reproducibility from a nonexistent seed flag.
2. Separate the data-generating mechanism from the model-training pipeline.
3. Include stochastic noise and interactions.
4. Avoid a single deterministic "dropout score" column.
5. Avoid direct leakage such as final completion status, post-dropout visits, or future measurements.
6. Keep dropout prevalence plausible for the artificial scenario but label it as a design choice, not an empirical estimate.
7. Include controlled missingness and explain whether it is random or feature-dependent.
8. Define at least one deliberately nonlinear relationship so tree models have something meaningful to compare with logistic regression.
9. Preserve hidden generator state only for generator validation; do not export it as a model feature.
10. Generate only fictional values and identifiers.
11. Generate typed patient/trial inputs first, call the existing pure screening domain engine, and
    freeze the synthetic linkage before generating longitudinal events or outcomes. Product
    database materialization, if required, belongs to the bounded R5 service workflow.
12. Use the frozen single-pass protocol, which designs every generated participant to satisfy its
    condition-specific canonical screening. Report requested, attempted, accepted, rejected, and
    unfilled counts; never use a future dropout outcome during acceptance. If this assumption ever
    changes, introduce a new generator version and document any resampling separately.
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

The accepted 20-enrollment smoke cohort contains 4 synthetic dropouts (20%). The accepted
400-enrollment demo contains 64 (16%): 45/280 in training, 10/60 in validation, and 9/60 in test.
The 400-enrollment cohort is the bounded product-facing dataset whose enrollment links may be
materialized for R5. The 4,000-enrollment experiment cohort is an offline versioned review
candidate; its linkage manifest supports reproducibility and training, not bulk
ordinary screening history.

The generator does not force an exact prevalence. Report the generated prevalence and event count
for every split and never adjust the test set after inspection. Observed prevalence is an
artificial run statistic, not model performance or a clinical estimate.

### 9.7 Split strategy

- Use one participant-level stratified 70/15/15 train/validation/test split for the primary R3
  artifact. Every enrollment for one participant follows that participant into the same split.
- Fit preprocessing on training data only.
- Freeze the primary test split before model tuning.
- Use cross-validation only on training/validation data.
- A second generator-run, site holdout, or changed-coefficient/missingness stress cohort is an
  optional R4 robustness experiment, not an R3 dataset-acceptance requirement. If performed, it
  receives a separate run identifier and report rather than being described as a repeated project
  seed.

### 9.8 Artifacts and documentation

- Versioned dataset schema.
- Generator configuration.
- Field-level provenance identifying deterministic, statistical, expression-derived, and optional
  LLM-generated columns.
- NVIDIA Data Designer recipe, package version, local execution/model-usage summary, and validation
  report. The current sampler-and-expression route reports zero model requests; never record
  credentials or restricted prompts.
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

- The exact Data Designer configuration, package version, local execution/model-usage metadata, and
  output validation report are recorded. The current sampler-and-expression route does not expose
  a project seed through the CLI, so the dataset is not described as byte-for-byte reproducible
  from a seed flag.
- IDs are unique and fictional.
- Dates follow the declared ordering.
- No post-cutoff feature leakage.
- Dropout labels agree with event times.
- Every enrollment resolves to exactly one internally consistent synthetic snapshot/trial/screening
  identifier set and a `potentially_eligible` canonical domain-engine result. Database-backed
  product resolution is tested when the bounded R5 linkage is materialized.
- Linkage metadata cannot change when risk predictions are regenerated.
- Censoring is internally consistent.
- Values and units stay in declared artificial ranges.
- Train/validation/test participants do not overlap.
- Hidden generator labels are excluded from exported model features.
- Missed-dose scenario edits recompute every dependent adherence feature.
- The Data Designer run succeeds locally; the sampler-and-expression configuration records zero
  LLM/model requests and requires no NVIDIA API key.
- NeMo output conforms to the same schema and invariant checks as the reviewed contract.
- No LLM-generated field directly or indirectly determines the label.
- Repository and public-demo scans contain no Track B rows, governed derivatives, access tokens,
  or fitted restricted-data artifacts.

### Exit criteria

- The dataset card and feature dictionary are understandable without reading generator code.
- Leakage tests pass.
- Outcome prevalence and split event counts are reported.
- The dataset card reports enrollments and dropout prevalence by linked trial version.
- The report names which columns used NeMo Data Designer and demonstrates that the label came from
  the reviewed sampler draw and dependent expression while the split and feature views remained deterministic.
- Track B is either backed by a recorded legitimate row-level source and separate protocol or
  clearly marked unavailable; synthetic generation does not masquerade as external validation.
- The user approves the artificial assumptions before model training begins.

### Stop point

Pause for review of the generated dataset report before implementing model experiments.

### Status

Complete and accepted as of 2026-08-15. The table-aware Data Designer 0.8.0 configuration, frozen
`r3-dataset-contract-v1`, 20-enrollment smoke cohort, 400-enrollment demo cohort, and 4,000-row
experiment candidate are complete. The experiment contains 702 synthetic dropouts (17.55%) and
passes schema, linkage, immutable-snapshot, split, chronology, censoring, relationship, and leakage
validation with zero hosted model requests. EDA, dataset card, feature dictionary, linkage
manifest, checksum evidence, and the dataset-generation workflow diagram are complete. The accepted
day-30 landmark view was used for R4.

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

Run both locked tree-model comparisons. The later R5 risk API packages the user-selected XGBoost
runtime model after review; it does not retroactively change the frozen validation selection.

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
- `r5_runtime` for the separately approved runtime package.

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
- No Track B model can become the configured runtime model for the multi-condition Scenario Lab,
  and no Track A model can be reported as externally validated.

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

- The separately approved runtime model has immutable package and threshold metadata.
- The evaluation report includes all required metrics and limitations.
- The model can be loaded in a clean process and reproduce inference.
- No prediction is described as clinically validated.

### Stop point

Pause for user approval of metrics, model choice, threshold, and presentation wording before adding runtime inference.

### Status

The manual Kaggle experiment completed on 2026-08-15 over the frozen 2,800/600/600
train/validation/test split. All four required model families were evaluated. The original frozen
validation rule selected LightGBM (`lightgbm-04`) because validation AUPRC was the primary metric
with Brier score as the tie-breaker. XGBoost (`xgboost-05`) produced the strongest observed
frozen-test results (AUROC 0.6807, AUPRC 0.3617, Brier 0.1331) and is the user-selected R5
runtime/product model. That product decision does not retroactively make XGBoost
validation-selected.

Both tree models received 1,000-repeat bootstrap uncertainty estimates and global/local SHAP
analysis. The local LightGBM MLflow record retains its historical `champion` alias but is not the
R5 runtime model. The experiment is complete; the committed experiment report records its protocol,
results, limitations, and R5 handoff. Binary model/MLflow artifacts remain local and ignored until
R5 explicitly packages XGBoost.

## 11. Phase R5 — Versioned research-risk API and UI

### Objective

Expose the user-selected XGBoost runtime model through a versioned research API and an integrated
action in the saved screening workspace, without coupling the prediction to the deterministic
screening decision.

The authoritative ingestion-to-runtime bridge for R5 and R6 is
[`docs/research-integration-contract.md`](../docs/research-integration-contract.md). It supersedes
the earlier proposal to select or link an R3 artifact row at runtime. R3 rows remain model-training
and evaluation lineage only.

### Screening-integrated interaction contract

1. A CRC opens an existing saved screening and independently selects **Start research follow-up**
   or **Predict dropout risk**.
2. TrialSync resolves the immutable patient snapshot, approved trial version, canonical screening,
   and platform-owned research enrollment.
3. Baseline fields already present in the snapshot and screening context are prefilled.
4. Day-30 follow-up fields are loaded from linked research events when available; otherwise the
   same panel requests the missing adherence, visit, adverse-event, and updated-severity inputs.
5. Missing day-30 information remains explicitly missing. It must never be silently converted to
   zero, because zero means an observed absence such as no missed visits.
6. The backend constructs and validates the exact day-30 feature snapshot before inference.
7. The screening workspace displays probability, threshold, horizon, model version, and top SHAP
   contributions beside—but not inside—the eligibility result.

The current model is a day-30 model. Screening data can start and prefill the workflow, but a
prediction must not be described as an immediate day-0 prediction unless a separate baseline-only
model is trained and versioned for that question.

### Data model

Required entities:

- `research_enrollments`, joining one owner-scoped saved screening to its immutable patient
  snapshot and approved trial version, with day-0 baseline values and explicit sources;
- append-only `research_dose_events`, `research_visit_events`, `research_measurements`, and
  `research_adverse_events`, including correction provenance through `supersedes_event_id`;
- immutable `research_follow_up_snapshots`, containing the exact derived 27-feature values,
  sources, missing fields, contributing-event checksum, and cutoff;
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
  - research enrollment and follow-up snapshot IDs;
  - model version;
  - feature snapshot JSON/hash;
  - probability;
  - thresholded research label;
  - top SHAP contributions;
  - prediction timestamp;
  - synthetic/research disclaimer version.

The enrollment record provides the immutable join to its patient snapshot, approved trial version,
and canonical screening. The 4,000-row training checksum stays in model provenance and never
identifies a runtime participant. Dose/visit rates and follow-up aggregates are server-derived from
events; missing denominators remain incomplete. Do not attach mutable risk fields to `screenings`
or `patients`.

### API

Candidate routes:

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
    "model_version": "dropout-xgboost:1",
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
    "name": "dropout-xgboost",
    "version": "1",
    "alias": "r5_runtime"
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
- Derive chart bands from the configured runtime model's versioned threshold/band policy.
- Do not call Gemini or Groq.
- Do not trigger screening.
- Do not convert probability into `potentially_eligible`, `likely_ineligible`, or `needs_review`.
- Do not permit prediction creation for arbitrary real records.
- Resolve trial-overview risk aggregates only through the immutable research-enrollment linkage.
- Prefill only fields resolved from the screening's immutable snapshot and approved trial version.
- Require an explicit source for every day-30 follow-up field and preserve that source in the
  versioned feature snapshot.
- Reject incomplete feature snapshots rather than interpreting unavailable follow-up data as zero.

### Frontend

Integrate dropout prediction into the existing saved-screening workspace:

- **Predict dropout risk** action on an authorized saved screening.
- Baseline fields prefilled from the immutable patient snapshot and trial-version context.
- Day-30 follow-up form for fields that are not already available from linked research events.
- Explicit incomplete-data state when required follow-up information is unavailable.
- Model card with dataset, horizon, metrics, threshold, and limitations.
- Risk result with probability, threshold, and top SHAP contributions.
- Eligibility result and evidence remain visible and unchanged in the same workflow.
- Trial Recruitment Overview with a trial selector, total screening-state counts, and a compact
  chart of linked potentially eligible participants by dropout-risk band.
- Visible numerator/denominator labels showing how many potentially eligible screenings have a
  linked research enrollment and prediction.
- Link to model version and feature definitions.
- Clear visual distinction between the deterministic eligibility result and the research-risk
  panel within the screening workspace.

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
- Screening-to-enrollment link resolution and baseline prefill.
- Missing day-30 inputs remain incomplete and are never silently zero-filled.
- Submitted follow-up values produce the expected versioned feature snapshot.
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
- Saved screening before prediction, with baseline prefill and missing follow-up fields.
- Saved screening after a completed day-30 prediction.
- Screening with no research-enrollment link and screening with incomplete follow-up data.
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
- A CRC can initiate and review dropout prediction from the saved-screening workspace without
  navigating to a disconnected prediction tool.
- Screening context is prefilled, required day-30 information is explicit, and unavailable values
  are never treated as observed zeros.
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

The active 750-member run is a stable reference landscape. Ordinary saved screenings query that
landscape through the projection contract; they are not manually mapped to a generated member and
do not mutate the sealed run.

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
POST /api/v1/research/screenings/{screening_id}/cohort-context
POST /api/v1/research/similarity/queries
POST /api/v1/research/screenings/{screening_id}/similarity
GET  /api/v1/research/similarity/queries/{query_id}
```

Saved-screening requests build patient-fact and, when selected, screening-profile vectors with the
active run's frozen preprocessing. Screening-profile construction calls the pure engine against
the 20-trial panel in memory. DBSCAN has no native prediction method, so external association uses
the versioned core-sample/`eps` rule and can return `unassigned`. FAISS accepts the external
normalized vector directly. Both responses retain feature, preprocessing, subject-order, and
reference-panel checksums.

### Frontend

- Cohort Atlas with a patient-fact/screening-profile representation switch.
- Seeded PCA projection for display only; DBSCAN and FAISS stay in full feature space.
- One patient node per unique snapshot, neutral noise nodes, and restrained cluster colors.
- FAISS edges only from the selected patient to its nearest neighbors.
- Cluster-size and noise summary.
- Structured participant table with cluster filters.
- Similar-patient side panel with exact fact or criterion-state differences.
- Three separate saved-screening actions for dropout prediction, cohort context, and similarity;
  choosing one does not execute or require either of the others.
- Links from screening-profile dimensions to canonical criterion evidence.
- Prominent statement that similarity is not eligibility evidence.

### Tests

- Same patient/reference-panel seeds produce identical matrix checksums.
- 15,000 evaluations collapse to exactly 750 cohort members.
- Materialized results agree with direct calls to the single-screening engine.
- Saved-screening projections agree with direct feature construction and do not create ordinary
  screening rows for the reference panel.
- Out-of-sample DBSCAN association returns a deterministic cluster or explicit unassigned state.
- External-vector FAISS results agree with brute-force cosine neighbors.
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

### Active V3 runtime cohort

The separately versioned V3 controlled cohort keeps the reference panel, feature builders,
bounded DBSCAN analysis, and exact CPU FAISS implementation fixed. Its group assignment is sealed
outside patient facts, feature matrices, selection, runtime APIs, and frontend payloads. The
750-member by 20-trial V3.1 run `r6-v3-6091f06c-542d-5b00-8bdc-6fbd782c9510` passed seal, DBSCAN,
FAISS, and runtime-readability review and is the approved R6 runtime cohort. Earlier R6 experiments
are retired provenance. See [`docs/r6-v3-controlled-cohort.md`](../docs/r6-v3-controlled-cohort.md)
for the contract.

## 12A. Phase R5A — Frontend experience redesign

### Objective

Replace the current implementation-centric interface with a compact, consistent, task-led
experience across authentication, dashboard, patient/trial ingestion, record review, screening,
dropout follow-up, population dropout review, and cohort exploration.

The authoritative implementation contract is
[`r5a-frontend-experience-redesign-plan.md`](r5a-frontend-experience-redesign-plan.md). It records
the approved information architecture, content rules, bounded backend additions, one preflight,
seven reviewable implementation stages, route-level behavior, verification requirements, and stop
points.

### Sequencing and boundaries

- R5A begins after the implemented R5/R6 integration and before R7.
- It preserves the completed patient-data semantic contract while replacing its presentation where
  required for one consistent ingestion flow.
- It may add bounded owner-scoped dashboard/dropout aggregates and cohort display summaries.
- It does not alter deterministic eligibility, retrain `xgboost-06`, or rebuild/overwrite the
  configured R6 run merely for presentation.
- The R5A preflight and each implementation stage stop for user review before continuing.

### Exit criteria

- The user accepts the preflight and all seven R5A implementation stages.
- Primary pages contain only task-relevant information by default.
- Manual and imported patient/trial data converge into consistent canonical review flows.
- The Overview is an interactive at-a-glance dashboard rather than a screening-count landing page.
- Dropout is useful both from one saved screening and from a potentially eligible screening
  worklist.
- The Cohort Atlas is an interactive patient graph with visible groups, human labels, search,
  filters, selection, and exact-neighbor context.
- Full automated and desktop/narrow-laptop/tablet visual acceptance passes.

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
are supplied to the manually deployed backend through its protected host environment. A protected
GitHub environment becomes relevant only if automated CD is implemented later.

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
5. Generator provenance and NeMo Data Designer configuration/validation evidence.
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
6. From the saved screening, open the integrated dropout-risk panel.
7. Show the prefilled screening context, enter or load the required day-30 follow-up fields, and
   run one dropout-risk prediction.
8. Show the approved model card, probability, threshold, and top SHAP contributions beside the
   unchanged eligibility result.
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
- NVIDIA Data Designer for R3, with its license, Python support, dependency weight, local execution
  mode, and optional provider boundary documented.
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
feat: add versioned NeMo-backed synthetic participant generator
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
- [x] The public synthetic dropout label is sampled by the reviewed Data Designer uniform sampler
  and dependent expression; TrialSync owns deterministic linkage, censoring, splits, views, and
  validation. No duplicate offline Python simulator is maintained.
- [x] NCT02054715-D1 is a future, separate study-specific adapter and never inflates the public
  synthetic cohort or its real-world evidence claim.
- [x] Dummy, logistic, XGBoost, and LightGBM are compared before the runtime-model decision.
- [x] MLflow uses a private optional Compose profile.
- [x] Aggregate research analytics use clearly labelled research navigation; participant-level
  dropout prediction is integrated into the saved-screening workspace.
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
| R3. Synthetic dropout protocol/dataset | Complete | User accepted the frozen generation contract and final 4,000-enrollment artifact before running R4 | Frozen contract; accepted smoke/demo/experiment artifacts; 702 synthetic dropouts; EDA, dataset card, feature dictionary, leakage audit, linkage manifest, checksums, and workflow diagram complete |
| R4. Dropout models/MLflow/SHAP | Complete | User completed and reviewed the manual Kaggle workflow on 2026-08-15 | Frozen-split comparison of dummy, logistic regression, XGBoost, and LightGBM; original validation rule selected LightGBM, while the user selected XGBoost `xgboost-05` for R5 runtime; calibration, threshold metrics, 1,000-repeat bootstrap intervals, SHAP, reproducibility metadata, MLflow artifacts, and committed experiment report complete |
| R5. Research-risk API/UI | In progress | User selected the XGBoost runtime model and requested a full platform enrollment/event integration contract, 2026-08-21 | Active `xgboost-06`/v2 packaging, append-only baseline correction, explicit streak inputs, immutable day-30 snapshots, prediction APIs, saved-screening readiness/prediction/SHAP frontend, and Trial Recruitment Overview implemented; final browser-based visual review remains |
| R6. Screening-derived DBSCAN/FAISS cohorts | In progress | User selected cohort analytics, authorized V3, and requested saved-screening integration | V3.1 passed review; saved-screening projection, external DBSCAN association, exact external-vector FAISS query, independent saved-screening cohort/similarity views, and population Cohort Atlas implemented; final browser-based visual review remains |
| R5A. Frontend experience redesign | Awaiting review | User approved the R5A direction and accepted R5A-0 through R5A-2 plus the bounded shared-CSS audit, 2026-08-25 | R5A-3 unified patient/trial manual and import entry, inline catalog/terminology assistance, and common review steps implemented; frontend tests, lint, typecheck, build, and focused backend ingestion/catalog tests pass; desktop and narrow-laptop/tablet visual review remains |
| R7. LangChain/Gemini eligibility RAG | Approved | Corrected to the supplied project brief, 2026-07-26 | |
| R8. Evaluation/final delivery | Approved | User selected supporting engineering/evaluation, 2026-07-26 | |

Allowed statuses: `Awaiting review`, `Approved`, `Revise`, `Not authorized`, `In progress`, `Blocked`, `Complete`, `Skipped`, or `Deferred`.

R1–R4 are complete. The R5/R6 backend bridge, coordinated saved-screening actions, population-wide
Trial Recruitment Overview, and Cohort Atlas are implemented, but their current frontend is
superseded by the approved R5A direction. R5A is the next phase and its final visual acceptance will
serve as the frontend exit evidence for R5/R6. R7 remains approved but starts only after R5A.
Preserve the R7 and R8 stop points. There is no R9 in this extension plan.

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
