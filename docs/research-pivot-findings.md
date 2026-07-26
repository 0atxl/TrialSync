# TrialSync Research Pivot: Feasibility Findings and Recommended Scope

**Date:** 2026-07-19
**Status:** Feasibility findings; implementation scope selected on 2026-07-26
**Relationship to existing project:** Incremental extension of the completed TrialSync application; not a replacement or total rewrite.

This document preserves the feasibility evidence behind the pivot. The locked scope, phase order, dataset sizes, and exit criteria live in
[`research-extension-implementation-plan.md`](research-extension-implementation-plan.md). The concise decision rationale lives in
[`research-feasibility-rating-and-local-llm.md`](research-feasibility-rating-and-local-llm.md).

## Executive conclusion

The proposed pivot is valuable, but it should be presented as a research extension to TrialSync rather than as four independent production features.

The strongest incremental direction is:

1. Add ClinicalTrials.gov discovery, measured criterion retrieval, and a genuinely retrieval-augmented bounded generator.
2. Reuse the existing deterministic, evidence-backed screening engine.
3. Add reproducible synthetic dropout-risk experiments with logistic regression, XGBoost, LightGBM, SHAP, and MLflow.
4. Add research-only cohort embeddings, DBSCAN clustering, and FAISS patient similarity.
5. Add canonical PDF reporting, a separate research UI/API, CI, and final evaluation.

BioBERT is deferred from the selected implementation scope. It remains a possible future experiment only after one supervised task and a suitable labelled dataset are approved.

The current eligibility decision must remain deterministic. Machine-learning models, FAISS similarity, SHAP explanations, and LLM/RAG output may assist discovery or explain a result, but they must not silently approve evidence or change `pass`, `fail`, `unknown`, or the final screening state.

## Proposed research project

### Recommended title

> **TrialSync Research: Explainable Clinical-Trial Discovery, Deterministic Pre-screening, and Patient-Cohort Analytics**

If access to a valid participant-level dropout dataset is secured:

> **TrialSync Research: Explainable Trial Matching, Cohort Discovery, and Participant Retention-Risk Modeling**

### Safer product claim

Use “research-grade full-stack prototype” or “deployable academic platform” rather than “production clinical platform.” MIMIC-III is restricted credentialed data, and none of the proposed predictive models should be described as clinically validated or suitable for autonomous enrollment decisions.

## Dataset feasibility

### MIMIC-III

MIMIC-III contains deidentified ICU data for more than 40,000 patients, including diagnoses, procedures, medications, laboratory values, vital signs, and clinical notes. It is not a clinical-trial participant registry and does not provide trial enrollment or dropout outcomes.

Access requires PhysioNet credentialing, human-subjects/HIPAA training, and a data-use agreement. The raw database and restricted clinical notes must not be committed to Git, bundled into the public demo, or sent to hosted LLM APIs without explicit authorization.

Source: [PhysioNet MIMIC-III Clinical Database](https://physionet.org/content/mimiciii/1.4/)

### COVID-19 clinical-trials dataset

A ClinicalTrials.gov-derived COVID-19 dataset is useful for study-level information such as trial status, design, eligibility text, recruitment, and locations. It does not provide patient-level medical records linked to enrollment and dropout outcomes.

Use the Kaggle snapshot for a reproducible historical benchmark if its exact license and fields are verified. For current open-trial discovery, prefer the official ClinicalTrials.gov API v2, recording the source timestamp and study version.

Source: [ClinicalTrials.gov API](https://clinicaltrials.gov/data-about-studies/learn-about-api)

### Candidate participant-level retention datasets

The NCI NCTN/NCORP Data Archive includes a verified candidate for a bounded retention-risk research experiment: **NCT02054715-D1**, a randomized multimedia-versus-print psychoeducation study for patients with cancer who were eligible for clinical trials. Its published data dictionary includes a participant identifier, baseline demographics, cancer type, recent treatment history, education, income, marital status, study group, `Dropouttime` (`0=no dropout`, `1=dropout at follow-up 1`, `2=dropout at follow-up 2`), and a `Dropout` reason field. This is a genuine participant-level dropout outcome; it is not inferred from missing records.

It can support a narrowly framed prototype such as “research-only retention-risk prediction in the NCT02054715-derived study.” It cannot support a claim that the model predicts dropout across cancer trials or clinical trials generally: it is one study with one intervention context, and its event count and follow-up structure must be inspected after access is granted.

NCI now directs researchers to obtain NCTN/NCORP patient-level data through dbGaP. The data must therefore remain outside the repository, be used only under the applicable approval and data-use conditions, and never be sent to hosted model providers without explicit authorization.

Sources: [NCT02054715-D1 data dictionary](https://nctn-data-archive.nci.nih.gov/system/files/dataset/NCT02054715-D1/NCT02054715-D1-Data-Dictionary.pdf), [NCI NCTN/NCORP Data Archive](https://dctd.cancer.gov/research/networks/nctn/data-archive)

For future multi-study work, [Project Data Sphere](https://data.projectdatasphere.org/) provides de-identified patient-level randomized cancer-trial datasets. A dataset is suitable only after its study documentation confirms a usable completion/discontinuation outcome and baseline or pre-horizon predictors. When data are in CDISC SDTM form, inspect the Disposition (`DS`) domain: its standard fields record completion/discontinuation status, date, and primary reason. Do not assume every Project Data Sphere study includes a usable `DS` domain or compatible follow-up window. [CDISC disposition guidance](https://www.cdisc.org/standards/foundational/cdash/cdashig-v2-0)

### Central label problem

The proposed datasets do not support patient-level clinical-trial dropout prediction by themselves:

- MIMIC patients are ICU patients, not identified clinical-trial participants.
- Trial registry records describe studies, not individual enrolled participants.
- Discharge, mortality, readmission, or disappearance from MIMIC cannot be treated as trial dropout.
- A proxy label created from missing later records would be clinically and methodologically invalid.

Therefore, “predict patient trial dropout” remains blocked for the originally listed datasets, but NCT02054715-D1 is a viable controlled-access candidate for a narrowly scoped retention-risk experiment. Any selected dataset must include enrollment, follow-up, withdrawal/dropout, reason, and censoring information sufficient for the chosen prediction task.

## Feature-by-feature assessment

| Feature | Feasibility | Recommendation |
|---|---|---|
| Patient dropout prediction | Feasible as a reproducible synthetic fixed-horizon experiment; real-world validation needs an approved participant-level dataset | Implement the selected synthetic longitudinal protocol; retain NCT02054715-D1 only as a possible future external-validation dataset |
| XGBoost/LightGBM | Feasible when labels exist | Use time-aware feature windows, leakage controls, calibration, and model-versioned inference |
| SHAP explanations | Feasible | Explain predictive risk features only; do not call SHAP an eligibility score |
| DBSCAN cohort discovery | Feasible research module | Build versioned patient-fact and screening-profile vectors from synthetic screening data and report stability and interpretable summaries |
| FAISS similarity search | Feasible | Index the same approved cohort representations and label neighbors as research similarity, not evidence |
| BioBERT ICD extraction | Feasible after task definition | Deferred from the selected implementation scope |
| BioBERT eligibility matcher | Requires new labels | Deferred; do not train an opaque replacement for the deterministic engine |
| RAG over trial criteria | Strong fit | Implement and evaluate retrieval separately, then supply versioned retrieved context to a bounded citation-validated generator |
| Groq eligibility summary | Strong fit with controls | Ground it in stored screening evidence, validate structured citations server-side, and retain deterministic fallbacks for rate limits or provider failure |
| LangChain | Optional | A small provider/retriever interface may be simpler and more reproducible |
| Docker and GitHub Actions | Feasible | Add research profiles and CI checks without claiming clinical production readiness |
| PDF eligibility report | Strong fit | Generate from stored canonical screening JSON; LLM prose is supplementary |

## A. Dropout or retention-risk prediction

### What is scientifically required

For the selected synthetic longitudinal experiment, define and freeze:

- an index date;
- a prediction horizon, such as dropout within 30 or 90 days;
- the exact dropout event and reason taxonomy;
- censoring and competing events;
- a feature cutoff so post-outcome information cannot leak into training;
- patient-level and temporal train/validation/test splits.

The approved benchmark is a fixed-horizon binary task: use features available by day 30 to predict dropout by day 90. Survival modeling and controlled real-world validation are later research options, not implementation dependencies.

### Recommended model experiments

- Logistic regression as an interpretable baseline.
- XGBoost and LightGBM as tree-based baselines.
- Aggregated event-window features rather than pretending tree models consume raw sequences.
- AUROC, AUPRC, calibration, sensitivity, specificity, and subgroup performance.
- SHAP feature contributions for model explanation.
- MLflow runs containing dataset version, feature schema, code version, model parameters, metrics, and artifacts.

### API boundary

Add a separate research prediction response, for example:

```json
{
  "risk_type": "retention_risk",
  "risk_probability": 0.64,
  "horizon_days": 90,
  "model_name": "retention-risk-lightgbm",
  "model_version": "7",
  "model_alias": "champion",
  "explanations": [
    {"feature": "missed_followup_count_30d", "contribution": 0.21}
  ],
  "clinical_disclaimer": "Research prediction; not a clinical decision."
}
```

This endpoint must not mutate the screening result or convert a risk probability into eligibility.

MLflow currently recommends model aliases and tags for references such as `champion` and `challenger`. [MLflow Model Registry workflows](https://mlflow.org/docs/latest/ml/model-registry/workflow/)

## B. Cohort clustering and patient similarity

This is a feasible and visually compelling research extension built from synthetic screening data, not from the dropout-training table.

### Suggested pipeline

```text
unique synthetic patient snapshots + fixed approved trial panel
  -> exact existing deterministic screening engine
  -> versioned patient-fact and screening-profile vectors
  -> separate DBSCAN cluster runs
  -> separate exact FAISS indexes
  -> Cohort Atlas and similar-patient views
```

### Required safeguards

- Count each patient once in the cohort; a patient × trial result matrix is a feature representation, not extra patients.
- Encode `unknown` explicitly rather than treating it as pass, fail, or zero evidence.
- Freeze patient generator, trial versions, screening-engine version, feature schema, and random seed.
- Version the feature pipeline, embedding model, and FAISS index.
- Report cluster stability, noise points, and clinically interpretable summaries without asserting discovered phenotypes.
- Keep similarity separate from eligibility evidence.
- Exclude dropout outcomes, risk scores, chat text, and RAG output from cohort features.

FAISS supports exact and approximate dense-vector similarity search, including cosine similarity through normalized inner products. [FAISS repository](https://github.com/facebookresearch/faiss)

For the initial scale, an exact CPU index is sufficient. A vector database or separate microservice is not required.

## C. Deferred BioBERT experiment

**Scope decision:** Deferred on 2026-07-26 and not part of the approved extension implementation.

“ICD extraction” and “eligibility criterion matching” are different supervised tasks and should not be presented as one model objective.

MIMIC ICD codes can provide weak labels for document-level coding, but they do not provide span-level annotations or clinical-trial eligibility labels. Eligibility matching therefore needs a separately annotated dataset or a reviewed synthetic benchmark.

BioBERT was evaluated for biomedical NER, relation extraction, and question answering; its pretraining does not guarantee performance on this project’s clinical eligibility task. [BioBERT paper](https://arxiv.org/abs/1901.08746)

Reconsider it only after choosing one labelled task, securing a valid dataset, and defining a leakage-safe held-out evaluation. Any future output must remain reviewable and disconnected from final eligibility.

## D. RAG, Groq, and eligibility reports

This is the most natural extension of the existing TrialSync product.

### Recommended flow

```text
Trial source/API
  -> retrieve candidate trials and relevant criteria
  -> show retrieval score and source metadata
  -> coordinator reviews/selects a trial version
  -> existing deterministic screening
  -> canonical evidence-backed result
  -> optional Groq structured explanation
  -> PDF report generated from stored result
```

RAG should retrieve and rank candidates. It must not replace deterministic criterion evaluation.

The report generator should use the stored screening JSON as its source of truth. LLM-generated wording may supplement the canonical explanation, but it must not invent facts, citations, or outcome changes.

The current bounded screening assistant remains Groq-backed when available. Keep the existing rules:

- only one authorized screening per conversation;
- latest ten messages maximum;
- citations validated against stored evaluations;
- no database, web, MCP, code-execution, or write tools;
- refusal of diagnosis, treatment, enrollment advice, unrelated questions, and prompt injection;
- canonical fallback when the provider is disabled or fails.

Provider resilience must parse numeric or HTTP-date `Retry-After`, maintain a short in-process cooldown, bound concurrency, retry only within a small budget with jitter, and cache safe retrieval/extraction work. Do not cache patient-specific chat across users. Deterministic extraction and canonical explanation fallbacks remain usable during `429` responses; a local small model is not an automatic fallback.

LangChain is optional. It is not itself a research result; a direct retriever/provider interface will likely be easier to test and version.

## Recommended incremental architecture

Keep the existing modules for authentication, patients, snapshots, trial versions, criteria, deterministic screening, evidence, history, and bounded explanation chat.

Add separate research-oriented modules:

```text
research/
  trial_discovery/       # ClinicalTrials.gov adapter, retrieval, and bounded RAG
  dropout_data/           # synthetic longitudinal enrollment-event protocol
  risk_models/            # training, inference, SHAP, scenario analysis
  cohort_profiles/        # screening-derived vectors, DBSCAN, FAISS
  mlflow_tracking/        # runs, artifacts, model aliases
  provider_resilience/    # cooldown, retry, concurrency, and safe caches
```

Suggested data entities:

- `trial_source_records`: source, fetched timestamp, source version, checksum.
- `trial_retrieval_results`: query, candidate trial, rank, retrieval score, model/index version.
- `research_model_versions`: MLflow name, version, alias, feature schema, validation status.
- `research_predictions`: subject, model version, prediction horizon, output, explanation metadata.
- `cohort_runs`: feature pipeline version, embedding version, cluster parameters, metrics.
- `similarity_queries`: query embedding/index version and returned research neighbors.

Research outputs should be visibly labeled as research analytics and should not be conflated with screening evidence.

## Selected implementation sequence

The phase order is intentionally maintained only in
[`research-extension-implementation-plan.md`](research-extension-implementation-plan.md) so findings cannot drift into a second competing plan. In summary: canonical PDF reporting and CI come first, followed by the synthetic longitudinal dropout protocol, MLflow-tracked models, screening-derived cohorts and similarity, ClinicalTrials.gov RAG, and final hardening/evaluation.

## Claims to avoid

- “Automatically enrolls or rejects patients.”
- “Predicts clinical-trial dropout” when the dataset contains no trial dropout labels, or when evidence comes from a single study but the claim implies generalization.
- “Production-ready clinical AI.”
- “SHAP-based eligibility scoring.”
- “BioBERT matches eligibility criteria” without a labeled held-out matching dataset.
- “MIMIC data is public” without mentioning credentialed access and the data-use agreement.
- “The LLM verified eligibility.”

## Final recommendation

Proceed with the selected scope: **genuine trial-retrieval RAG + deterministic screening + grounded reporting** as the product centerpiece, with **synthetic dropout modeling, MLflow, SHAP, DBSCAN cohorts, and FAISS similarity** as clearly separated research analytics. BioBERT is deferred. Controlled-access NCT02054715-D1 work remains future external validation and is not an implementation dependency.

This approach adds meaningful research depth while preserving the architecture, tests, safety boundaries, and user experience already built in TrialSync.
