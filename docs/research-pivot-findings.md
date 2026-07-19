# TrialSync Research Pivot: Feasibility Findings and Recommended Scope

**Date:** 2026-07-19  
**Status:** Research and architecture recommendation  
**Relationship to existing project:** Incremental extension of the completed TrialSync application; not a replacement or total rewrite.

## Executive conclusion

The proposed pivot is valuable, but it should be presented as a research extension to TrialSync rather than as four independent production features.

The strongest incremental direction is:

1. Add trial discovery and criterion retrieval.
2. Reuse the existing deterministic, evidence-backed screening engine.
3. Add research-only cohort embeddings and patient similarity.
4. Add BioBERT experiments with a precisely defined supervised task.
5. Add dropout prediction only after obtaining a dataset with valid participant-level dropout labels.

The current eligibility decision must remain deterministic. Machine-learning models, FAISS similarity, SHAP explanations, and LLM/RAG output may assist discovery or explain a result, but they must not silently approve evidence or change `pass`, `fail`, `unknown`, or the final screening state.

## Proposed research project

### Recommended title

> **TrialSync Research: Explainable Clinical-Trial Discovery, Deterministic Pre-screening, and Patient-Cohort Analytics**

If a valid participant-level dropout dataset is later obtained:

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

### Central label problem

The proposed datasets do not support patient-level clinical-trial dropout prediction by themselves:

- MIMIC patients are ICU patients, not identified clinical-trial participants.
- Trial registry records describe studies, not individual enrolled participants.
- Discharge, mortality, readmission, or disappearance from MIMIC cannot be treated as trial dropout.
- A proxy label created from missing later records would be clinically and methodologically invalid.

Therefore, “predict patient trial dropout” is blocked unless a separate participant-level dataset includes enrollment, follow-up, withdrawal/dropout, reason, and censoring information.

## Feature-by-feature assessment

| Feature | Feasibility | Recommendation |
|---|---|---|
| Patient dropout prediction | Not valid with the listed datasets | Reframe as trial-level recruitment/termination risk, or defer until a valid participant-level dataset is available |
| XGBoost/LightGBM | Feasible when labels exist | Use time-aware feature windows, leakage controls, calibration, and model-versioned inference |
| SHAP explanations | Feasible | Explain predictive risk features only; do not call SHAP an eligibility score |
| DBSCAN cohort discovery | Feasible research module | Use fixed, normalized time windows and report cluster stability and clinical enrichment |
| FAISS similarity search | Feasible | Store embedding/index versions and label results as research similarity, not evidence |
| BioBERT ICD extraction | Feasible after task definition | Treat ICD coding, span extraction, and eligibility matching as separate tasks |
| BioBERT eligibility matcher | Requires new labels | Use annotated patient–criterion pairs or reviewed candidates; do not train an opaque replacement for the deterministic engine |
| RAG over trial criteria | Strong fit | Add retrieval before the existing screening workflow |
| Gemini eligibility summary | Strong fit with controls | Ground it in stored screening evidence and validate structured citations server-side |
| LangChain | Optional | A small provider/retriever interface may be simpler and more reproducible |
| Docker and GitHub Actions | Feasible | Add research profiles and CI checks without claiming clinical production readiness |
| PDF eligibility report | Strong fit | Generate from stored canonical screening JSON; LLM prose is supplementary |

## A. Dropout or retention-risk prediction

### What is scientifically required

If a valid participant-level dataset becomes available, define:

- an index date;
- a prediction horizon, such as dropout within 30 or 90 days;
- the exact dropout event and reason taxonomy;
- censoring and competing events;
- a feature cutoff so post-outcome information cannot leak into training;
- patient-level and temporal train/validation/test splits.

Although the initial proposal says binary classification, time-to-event or survival modeling may be more appropriate when follow-up duration varies. A binary model can still be used for a fixed horizon as an explicit benchmark.

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

This is a feasible and visually compelling research extension.

### Suggested pipeline

```text
MIMIC event tables
  -> approved feature extraction
  -> aligned time windows with missingness masks
  -> trajectory embeddings
  -> DBSCAN clusters
  -> FAISS vector index
  -> cohort explorer and similar-patient view
```

### Required safeguards

- Normalize units and sampling intervals.
- Handle irregular observations and missing values explicitly.
- Prevent future events from entering an index-time embedding.
- Version the feature pipeline, embedding model, and FAISS index.
- Report cluster stability and clinically interpretable cluster summaries.
- Keep similarity separate from eligibility evidence.
- Never expose restricted MIMIC text or identifiers in a public deployment.

FAISS supports exact and approximate dense-vector similarity search, including cosine similarity through normalized inner products. [FAISS repository](https://github.com/facebookresearch/faiss)

For the initial scale, an exact CPU index is sufficient. A vector database or separate microservice is not required.

## C. BioBERT experiments

“ICD extraction” and “eligibility criterion matching” are different supervised tasks and should not be presented as one model objective.

### Possible tasks

1. **ICD prediction:** multi-label document classification from clinical notes.
2. **Clinical entity extraction:** token/span classification for diagnoses, medications, observations, or procedures.
3. **Patient–criterion matching:** pair classification or ranking using explicitly annotated pairs.

MIMIC ICD codes can provide weak labels for document-level coding, but they do not provide span-level annotations or clinical-trial eligibility labels. Eligibility matching therefore needs a separately annotated dataset or a reviewed synthetic benchmark.

BioBERT was evaluated for biomedical NER, relation extraction, and question answering; its pretraining does not guarantee performance on this project’s clinical eligibility task. [BioBERT paper](https://arxiv.org/abs/1901.08746)

### Recommended evaluation

- Split by patient, not by note, to prevent leakage.
- Compare BioBERT with a simple terminology/regex baseline and optionally ClinicalBERT.
- Report micro-F1, macro-F1, per-label precision/recall, and error categories.
- Preserve source spans and confidence as reviewable candidates.
- Never allow the model to set the final screening state.

PhysioNet also provides expert-annotated MIMIC phenotype notes that could support a narrower supervised NLP experiment, subject to the same credentialed-access and data-use requirements. [MIMIC phenotype annotations](https://physionet.org/content/phenotype-annotations-mimic/1.20.3/)

## D. RAG, Gemini, and eligibility reports

This is the most natural extension of the existing TrialSync product.

### Recommended flow

```text
Trial source/API
  -> retrieve candidate trials and relevant criteria
  -> show retrieval score and source metadata
  -> coordinator reviews/selects a trial version
  -> existing deterministic screening
  -> canonical evidence-backed result
  -> optional Gemini/Groq structured explanation
  -> PDF report generated from stored result
```

RAG should retrieve and rank candidates. It must not replace deterministic criterion evaluation.

The report generator should use the stored screening JSON as its source of truth. LLM-generated wording may supplement the canonical explanation, but it must not invent facts, citations, or outcome changes.

Gemini supports JSON-schema structured output, but schema compliance alone does not guarantee semantic correctness. Validate criterion IDs, evidence IDs, quotations, values, and answer scope in backend code. [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)

The current bounded screening assistant can become provider-neutral across Groq and Gemini. Keep the existing rules:

- only one authorized screening per conversation;
- latest ten messages maximum;
- citations validated against stored evaluations;
- no database, web, MCP, code-execution, or write tools;
- refusal of diagnosis, treatment, enrollment advice, unrelated questions, and prompt injection;
- canonical fallback when the provider is disabled or fails.

LangChain is optional. It may help with orchestration, but it is not itself a research result. A direct retriever/provider interface will likely be easier to test and version.

## Recommended incremental architecture

Keep the existing modules for authentication, patients, snapshots, trial versions, criteria, deterministic screening, evidence, history, and bounded explanation chat.

Add separate research-oriented modules:

```text
research/
  trial_discovery/       # ClinicalTrials.gov/Kaggle adapters and retrieval
  risk_models/            # training, inference, SHAP, model metadata
  cohorts/                # trajectory features, DBSCAN, embeddings, FAISS
  nlp_experiments/        # BioBERT training and held-out evaluation
  mlflow_tracking/        # runs, artifacts, model aliases
```

Suggested data entities:

- `trial_source_records`: source, fetched timestamp, source version, checksum.
- `trial_retrieval_results`: query, candidate trial, rank, retrieval score, model/index version.
- `research_model_versions`: MLflow name, version, alias, feature schema, validation status.
- `research_predictions`: subject, model version, prediction horizon, output, explanation metadata.
- `cohort_runs`: feature pipeline version, embedding version, cluster parameters, metrics.
- `similarity_queries`: query embedding/index version and returned research neighbors.

Research outputs should be visibly labeled as research analytics and should not be conflated with screening evidence.

## Suggested implementation phases

### Research Phase 0: protocol and governance

- Decide whether the project will use only synthetic data publicly or also run a private credentialed MIMIC workflow.
- Record PhysioNet approvals and data-use constraints before downloading MIMIC.
- Define research questions, target labels, splits, metrics, and leakage controls.
- Confirm the Kaggle dataset’s exact fields and license.

### Research Phase 1: trial discovery and reports

- Add an official ClinicalTrials.gov API adapter.
- Store source timestamps and raw-source checksums without exposing restricted patient data.
- Retrieve candidate trials and criteria.
- Reuse the existing review workflow and deterministic screening.
- Add a PDF report generated from canonical stored results.

### Research Phase 2: experiment tracking

- Add MLflow locally or in a controlled development environment.
- Track dataset, feature, code, model, metrics, and artifact versions.
- Add a model registry with `champion` and `challenger` aliases.
- Add CI checks for training reproducibility and inference schema compatibility.

### Research Phase 3: BioBERT task

- Select exactly one initial task: ICD classification, entity extraction, or criterion retrieval.
- Build a leakage-safe held-out evaluation.
- Keep model output reviewable and disconnected from final eligibility.

### Research Phase 4: cohort explorer

- Build trajectory features and embeddings.
- Run DBSCAN with stability checks.
- Build a versioned FAISS index.
- Add cohort and similarity views with research-only labels.

### Research Phase 5: valid retention-risk model

- Proceed only after securing participant-level dropout labels.
- Implement a fixed-horizon binary baseline and, if appropriate, a survival model.
- Add calibration, subgroup analysis, SHAP, MLflow registry, and a versioned API.

## Claims to avoid

- “Automatically enrolls or rejects patients.”
- “Predicts clinical-trial dropout” when the dataset contains no trial dropout labels.
- “Production-ready clinical AI.”
- “SHAP-based eligibility scoring.”
- “BioBERT matches eligibility criteria” without a labeled held-out matching dataset.
- “MIMIC data is public” without mentioning credentialed access and the data-use agreement.
- “The LLM verified eligibility.”

## Final recommendation

Proceed with the pivot, but make **trial discovery + deterministic screening + grounded reporting** the product centerpiece. Treat **cohorts, BioBERT, and MLflow** as research analytics modules. Defer or reframe **patient dropout prediction** until a valid outcome dataset exists.

This approach adds meaningful research depth while preserving the architecture, tests, safety boundaries, and user experience already built in TrialSync.
