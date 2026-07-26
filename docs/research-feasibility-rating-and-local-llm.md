# TrialSync Research Feasibility, Project Assessment, and Local LLM Decision

**Date:** 2026-07-26
**Status:** R0 decision brief approved on 2026-07-26; R1 is the next implementation phase
**Purpose:** Record the practical feasibility audit, an intentionally blunt academic
assessment, and the local-versus-hosted LLM recommendation before the research extension
is implemented.

## 1. Executive verdict

The proposed extension is practical for one BTech final-year project if it is delivered
phase by phase and the synthetic-data claim remains explicit. It is not practical if the
existing screening rows are relabelled as longitudinal trial-participant records.

The central conclusions are:

1. TrialSync's current patient snapshots and screening evaluations are useful inputs for
   patient clustering and similarity. The unit must remain one unique patient/profile, not
   one patient × trial row.
2. Those screening records are not a dropout dataset. A separate, reproducible, event-level
   synthetic enrollment cohort is required only for dropout modeling and scenario analysis.
3. The research extension therefore needs two explicit datasets: a screening-derived cohort
   for DBSCAN/FAISS and a longitudinal enrollment dataset for dropout prediction.
4. Missed-dose what-if visualization is feasible and valuable, but it is model sensitivity,
   not a causal treatment-effect estimate.
5. DBSCAN and exact CPU FAISS are technically easy at semester scale. Honest feature design,
   stability evaluation, and the frontend Cohort Atlas are the harder and more valuable work.
6. ClinicalTrials.gov RAG is feasible if retrieval remains deterministic and measurable,
   generation is bounded to retrieved records, citations are validated, and a cached corpus
   supports offline use.
7. `alsomine` can execute the installed 1–1.5B Ollama models, but live measurements show that
   neither is reliable enough to replace Groq for grounded generation.
8. The preferred response to Groq 429s is a stronger rate-limit-aware provider gateway plus
   deterministic fallbacks, not an automatic switch to a weaker local model.
9. The current application is already stronger than a CRUD-and-chatbot demo, but its ML
   research contribution is limited. A well-executed extension can make it a strong BTech
   capstone; merely adding library names will not.

## 2. What the current repository actually contains

The current data model contains:

- mutable user-owned patient records and dated facts;
- immutable patient snapshots created for screening;
- immutable approved trial versions and criteria;
- one stored deterministic evaluation per patient-snapshot × trial-version pair;
- criterion evidence, missing-information requirements, and engine/version metadata;
- bounded explanation conversations attached to saved screenings.

The larger seeded workspace contains 20 patients, 15 approved trial versions, and 300
screening results. Those 300 rows are a complete 20 × 15 cross-product created on the same
screening date. They are not 300 independent trial participants.

The repository does not currently contain:

- enrollment episodes;
- scheduled and administered dose events;
- visit schedules and attendance events;
- longitudinal adverse events;
- repeated patient-reported burden measurements;
- protocol discontinuation or dropout events;
- censoring times;
- explicit dropout reasons;
- a valid pre-event observation cutoff and future prediction horizon.

### Why the 300 screenings are not 300 cohort members

Treating every screening as a separate cohort member would repeat the same 20 patients across
15 trials. The cohort sample size is 20 unique patient profiles, not 300. A cluster or similarity
index built from 300 rows would overweight each repeated patient and create misleading density.

The screening matrix is still useful when represented correctly. Each unique patient can have
one screening-profile vector across a fixed panel of approved trial versions. That produces 20
vectors from the current admin seed, with trial/criterion results forming dimensions of each
patient's profile.

The current 20-patient cohort is sufficient for a UI fixture, not for a convincing DBSCAN
stability study. A larger set of synthetic patient records should be generated through the
existing patient/fact schema and evaluated against the same fixed approved trial panel.

Screening results must not be converted into dropout labels. Eligibility criteria, criterion
failures, and missing evidence also must not become post-hoc substitutes for actual
participation history.

### Appropriate use of screening data

Existing data can directly support the cohort/similarity research:

- one unique patient snapshot becomes one cohort member;
- normalized facts create a patient-fact representation;
- deterministic results across a fixed trial panel create a screening-profile representation;
- pass/fail/unknown patterns and missing-information categories can describe why two profiles
  are similar;
- the UI can link every screening-profile dimension back to its canonical criterion evidence.

This is separate from dropout modeling. A research enrollment needs generated longitudinal
events and an actual synthetic dropout/censoring outcome. Screening IDs and criterion results
must not become dropout-model features.

## 3. A viable synthetic dropout dataset

### 3.1 Research unit

One row in the dropout-modeling cohort represents one synthetic participant enrolled in one
synthetic trial context. It is not one screening result and it is not part of the
screening-profile cohort.

Each participant should have:

- an enrollment date;
- a condition/trial category;
- baseline demographics and normalized burden features;
- a scheduled dose and visit calendar;
- generated administered/missed dose events;
- attended, delayed, and missed visits;
- longitudinal severity or burden measurements;
- adverse-event events;
- observation/missingness events;
- a dropout or censoring event after the observation cutoff.

### 3.2 Multi-condition portfolio

The research story should not be oncology-only. The planned generator should cover a small,
declared portfolio such as:

- metabolic/type 2 diabetes;
- cardiovascular/hypertension;
- renal disease;
- oncology;
- respiratory disease.

The exact categories can be aligned with the final TrialSync demonstration data. The current
checked-in admin seed is mainly metabolic, diabetes, renal, lipid, and hypertension oriented;
it is not yet a genuinely broad disease portfolio.

Disease-specific raw measures must remain condition-specific. HbA1c, tumour burden, eGFR,
and respiratory-function measurements cannot be placed into one vector as if their raw
values were interchangeable. Cross-condition research features should instead use documented
representations such as:

- normalized baseline burden;
- latest pre-cutoff burden;
- burden slope and variability;
- treatment burden;
- dose-adherence rate;
- visit-adherence rate;
- adverse-event burden;
- travel/access burden;
- patient-reported burden;
- measurement missingness.

The original raw synthetic values should remain available for display and audit.

### 3.3 Time and outcome contract

A practical first experiment is:

- enrollment: day 0;
- observation cutoff: day 30;
- prediction target: dropout between day 31 and day 90;
- censoring: no known dropout through day 90;
- target prevalence: a documented synthetic design parameter, initially about 25%.

The cutoff and horizon are design choices, not estimates of real clinical-trial behavior.

No event after day 30 may become an input feature. Dropout reason, dropout date,
post-dropout missed visits, and final completion state are forbidden model features.

### 3.4 Generation approach

The generator should use an explicit stochastic process:

1. Sample baseline participant, site, and trial-context variables.
2. Generate scheduled visits and doses.
3. Generate pre-cutoff adherence, burden, adverse events, and missingness with noise and
   declared interactions.
4. Compute a hidden stochastic dropout hazard from selected pre-cutoff and latent variables.
5. Sample dropout time rather than directly copying a deterministic score into the label.
6. Continue only valid observations until dropout or censoring.
7. Export the hidden generator state separately for generator validation, never as model input.

At least one nonlinear interaction should exist so that tree models have something meaningful
to compare with logistic regression. For example, missed doses may matter more when treatment
burden and travel burden are both high. Random noise must remain substantial enough that the
target is not trivial.

### 3.5 Dataset sizes

A workable staged design is:

| Dataset | Suggested size | Purpose |
|---|---:|---|
| Tiny fixture | 30–50 participants | Unit and schema tests |
| Demo cohort | 250–500 participants | Frontend and fast inference |
| Experiment cohort | 3,000–5,000 participants | Model comparison and stability evaluation |

These sizes are easy for scikit-learn, XGBoost, LightGBM, DBSCAN, and exact FAISS on ordinary
CPU hardware. Increasing synthetic row count does not create additional real-world evidence;
it only improves numerical stability for the declared artificial experiment.

### 3.6 Scientific ceiling

The generator creates both the predictors and the outcome mechanism. Therefore the experiment
can demonstrate:

- reproducible data engineering;
- leakage-safe feature construction;
- baseline/model comparison;
- calibration and threshold plumbing;
- model-versioned inference;
- SHAP calculation;
- scenario analysis;
- cluster and similarity evaluation.

It cannot demonstrate that the model predicts real participant dropout. Strong scores mostly
show that the model recovered relationships intentionally placed in the generator.

To make the experiment less circular:

- freeze the generator before model tuning;
- use multiple generator seeds;
- include site-based or generator-regime holdouts;
- vary coefficients and missingness in a stress-test cohort;
- retain a dummy and logistic-regression baseline;
- report calibration and uncertainty, not only AUROC;
- describe restricted participant datasets as future external validation.

## 4. A viable screening-derived cohort and similarity dataset

### 4.1 Unit of analysis

The clustering and FAISS unit is one immutable synthetic patient snapshot evaluated against
one fixed, versioned reference panel of approved trials.

Two separately versioned representations are useful:

1. **Patient-fact space**
   - age band;
   - condition assertions;
   - medication assertions;
   - normalized observations;
   - evidence age and missingness.
2. **Screening-profile space**
   - one-hot pass/fail/unknown criterion results;
   - pass/fail/unknown rates by trial or criterion family;
   - missing-information categories;
   - optionally the result pattern across the fixed reference trial panel.

These representations answer different questions:

- patient-fact similarity asks which synthetic patients have similar recorded facts;
- screening-profile similarity asks which patients produce similar eligibility-evidence
  patterns across the same trial panel.

Neither representation is a dropout-training dataset.

### 4.2 How to create enough cohort data

The checked-in admin seed has only 20 unique patients and is weighted toward metabolic,
diabetes, renal, lipid, and hypertension protocols. The practical cohort build is:

1. Define a multi-condition synthetic patient schema compatible with TrialSync facts.
2. Generate 500–1,000 unique synthetic patient records with a fixed seed.
3. Define a fixed panel of 15–30 approved synthetic trial versions across the selected
   conditions.
4. Run the exact existing deterministic single-screening engine for every patient × trial
   pair in an offline research-materialization step.
5. Collapse the resulting matrix back to one feature vector per patient.
6. Fit preprocessing, DBSCAN, and FAISS only after the patient-level representation is frozen.

For example, 750 patients × 20 trial versions produces 15,000 deterministic screening
evaluations but still represents 750 cohort members. The offline research materialization
does not need to clutter ordinary user screening history with 15,000 saved product screenings.
It can store a versioned research matrix and provenance/checksums while continuing to call the
same pure screening engine.

### 4.3 Encoding and leakage controls

Categorical criterion states should be one-hot encoded rather than assigned a misleading
continuous ordering. `unknown` is not halfway between pass and fail.

The reference trial panel, criterion ordering, DSL version, engine version, terminology version,
and unit version must be frozen with the matrix. A changed trial version requires a new matrix
and FAISS index.

Do not use:

- the number of duplicated patient × trial rows as the sample size;
- dropout labels or dropout-model probabilities;
- hidden patient-generator classes;
- mutable chat text;
- generated RAG summaries.

### 4.4 Relationship to the frontend

The Cohort Atlas can expose a representation switch:

- **Clinical fact view** for fact-space DBSCAN and neighbors;
- **Screening profile view** for evidence-pattern DBSCAN and neighbors.

Selecting a neighbor should show the exact facts or criterion-state dimensions that contributed
to similarity. The result remains descriptive research analytics and never changes eligibility.

## 5. Dropout risk and the missed-dose Scenario Lab

The proposed what-if feature is feasible and should be a primary frontend demonstration.

### 5.1 Scenario calculation

For a selected synthetic participant:

1. Load the participant's event history through day 30.
2. Calculate the baseline feature vector and risk.
3. Add one plausible missed-dose event before the cutoff.
4. Recalculate all dependent features, including scheduled dose count, received dose count,
   adherence rate, recent missed-dose count, and applicable burden interactions.
5. Run the exact same approved model again.
6. Display the baseline, scenario risk, and model-output difference.

The interface should never directly edit a derived adherence percentage without updating its
underlying event history.

### 5.2 Visualizations

The Risk Scenario Lab should include:

- a baseline probability and threshold;
- a missed-dose sweep, such as 0–4 additional missed doses;
- an event marker for the selected scenario;
- baseline and scenario SHAP contribution bars;
- a percentage-point difference;
- model, dataset, feature, and scenario versions;
- a persistent synthetic/non-causal disclaimer.

A later temporal view may show a risk trajectory at several observation cutoffs with a
missed-dose event marker. That requires a feature pipeline valid at each cutoff and must not
silently mix different prediction horizons.

### 5.3 Correct claim

Allowed:

> Under model version X on the synthetic feature snapshot, one additional pre-cutoff missed
> dose changes estimated dropout risk from 18% to 27%.

Not allowed:

> Missing one dose causes this participant's dropout risk to increase by 9%.

SHAP and single-feature scenario changes describe model behavior. They do not establish a
causal effect or recommend an intervention.

## 6. Cohort clustering, similarity indexing, and the Cohort Atlas

### 6.1 DBSCAN

DBSCAN groups dense regions of the versioned research feature space and can leave unusual
participants as noise instead of forcing every participant into a cluster. The implementation
is straightforward; parameter selection and stability reporting are the meaningful research
work. The official scikit-learn API documents `eps`, `min_samples`, distance metrics, and
noise labels: [scikit-learn DBSCAN documentation](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html).

Both clustering representations must exclude:

- dropout label and dropout time;
- predicted dropout probability;
- hidden generator trajectory labels;
- post-cutoff events;
- any screening result outside the frozen reference panel.

For the patient-fact view, disease category may be excluded from the primary run and inspected
after clustering so it does not trivially dominate the map. For the screening-profile view,
criterion results are intentionally the research representation; the UI and report must call
the groups eligibility-evidence profiles, not clinical phenotypes.

### 6.2 FAISS

FAISS is a vector index, not a learned eligibility or dropout model. It stores fixed-dimensional
`float32` vectors and returns nearest neighbors; this matches the official
[FAISS getting-started contract](https://github.com/facebookresearch/faiss/wiki/getting-started).

For 500–1,000 synthetic patient profiles, use one exact CPU index per representation with
normalized vectors and inner product for cosine similarity. Approximate search and a vector
database would add complexity without academic value.

The index must record:

- dataset and participant-order checksum;
- feature/preprocessing version;
- vector dimension;
- distance metric and index type;
- build timestamp.

Every FAISS result should be verified in tests against brute-force cosine similarity.

### 6.3 Cohort Atlas frontend

The requested mind-map-like frontend is practical. The scientifically clearer name is
**Cohort Atlas**.

It should show:

- one node per synthetic participant;
- a restrained research color per DBSCAN cluster;
- neutral grey for noise;
- a clearly outlined selected participant;
- edges only from the selected participant to its nearest FAISS neighbors;
- optional cluster regions or hulls;
- filters for cluster, condition, site, and burden band;
- hover/focus summaries and a structured detail panel;
- an accessible table alternative.

DBSCAN and FAISS must operate in the full versioned feature space. A reproducible PCA or UMAP
projection may position nodes in two dimensions for display. The UI must state that screen
distance is approximate and exact neighbor scores come from the full feature vector.

Drawing every possible neighbor edge would create an unreadable graph. Cluster structure should
be visible globally, while neighbor edges appear only for the selected participant.

## 7. Why ClinicalTrials.gov genuine RAG remains useful

TrialSync currently screens trials that a user has already created or imported. It does not
discover current public trial records.

ClinicalTrials.gov API v2 exposes structured study records and an OpenAPI specification. The
official documentation describes the `/api/v2/studies` search endpoint and structured fields
such as NCT ID, recruitment status, conditions, age, locations, and eligibility:
[ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api) and
[study data structure](https://clinicaltrials.gov/data-api/about-api/study-data-structure).

The proposed pipeline is:

```text
User query or approved synthetic patient summary
  -> deterministic status/age/condition/location filters
  -> BM25 retrieval over a versioned cached corpus
  -> top bounded trial records and eligibility excerpts
  -> bounded LLM comparison using only retrieved context
  -> validate every NCT/criterion citation
  -> user selects a result
  -> existing review and approval workflow
  -> existing deterministic screening
```

RAG adds value because the generator receives a small, current, attributable evidence package
instead of relying on model memory. It also creates a separate retrieval research question with
Recall@k, Precision@k, mean reciprocal rank, filter correctness, citation validity, grounded
claim precision, and unsupported-claim counts.

RAG does not replace screening. Retrieval score is not eligibility, generated prose is not
evidence, and every selected trial still requires human review and approval.

The live API should update the corpus, but automated tests and the presentation fallback should
use a cached, checksummed public-record fixture. That keeps the demo working when the registry
or internet is unavailable.

## 8. MLflow, CI, and CD

### 8.1 Local MLflow

Local MLflow means self-hosted experiment tracking rather than a paid or externally hosted
tracking service.

For this project:

- use a SQLite-backed MLflow metadata store;
- use a local ignored artifact directory for model files and plots;
- run the MLflow server/UI through an optional Compose profile;
- bind it to localhost or an authenticated private route;
- never expose it as part of the public TrialSync user interface;
- copy only approved model metadata and aggregate metrics into the TrialSync research UI.

MLflow's official documentation supports a local database and filesystem artifacts for solo
development. It also notes that Model Registry functionality requires a database-backed store:
[local database tutorial](https://www.mlflow.org/docs/latest/ml/tracking/tutorials/local-database/),
[backend stores](https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/), and
[artifact stores](https://mlflow.org/docs/latest/self-hosting/architecture/artifact-store/).

### 8.2 Continuous integration

CI runs quality gates automatically on every push or pull request:

- backend lint, typing, migrations, and tests;
- frontend lint, typing, tests, and production build;
- deterministic research fixture tests;
- secret and dependency checks;
- optional container builds.

CI is valuable academic evidence even though it is not a visible product feature.

### 8.3 Continuous deployment

CD would automatically deploy a commit after CI succeeds. A responsible TrialSync CD workflow
would need deployment credentials, a database backup policy, migration handling, health gates,
and rollback behavior.

The current manual `alsomine` workflow is safer while the research schema is changing:

```text
push -> inspect -> SSH -> fast-forward pull -> Compose rebuild -> migration -> health checks
```

Recommendation: implement CI now and retain manual production deployment until the research
extension stabilizes. CD adds less academic value than the dataset, evaluation, RAG, or
visualization work.

## 9. Practicality by phase

| Phase | Practicality | Main risk | Honest effort for one student |
|---|---|---|---|
| R1 canonical PDF | High | deterministic pagination and long text | 3–5 focused days |
| R2 GitHub Actions CI | High | PostgreSQL/service setup and secrets | 2–4 focused days |
| R3 synthetic longitudinal protocol/dataset | Medium–high | invalid or trivially learnable generator | 1.5–2.5 weeks |
| R4 models, MLflow, SHAP | Medium–high | leakage, calibration, dependency weight | 2–3 weeks |
| R5 risk API and Scenario Lab | Medium–high | feature parity and non-causal wording | 1.5–2.5 weeks |
| R6 DBSCAN, FAISS, Cohort Atlas | Medium–high | patient-level matrix design, stability, and honest 2D visualization | 2–3 weeks |
| R7 ClinicalTrials.gov RAG | Medium–high | source drift, grounding, and provider resilience | 2.5–4 weeks |
| R8 integrated evaluation | High but substantial | clean reproducibility and presentation | 1.5–2.5 weeks |

The phases overlap somewhat, but the complete extension is roughly a 12–18 week part-time
project for one person working carefully. It is not a safe two-week feature sprint.

Recommended gating:

1. Implement R1 and R2 after R0.
2. Stop after R3 and inspect the dataset card, leakage audit, prevalence, and feature
   distributions.
3. Stop after R4 and inspect held-out metrics and calibration before exposing predictions.
4. Build R5 from the accepted dropout feature contract; build R6 independently from its
   screening-derived patient-profile contracts.
5. Build R7 independently with a frozen corpus and provider evaluation.
6. Integrate only after every component has a deterministic degraded mode.

## 10. Blunt project rating

No exact earlier conversational score is recoverable from the repository. The rating below is
based on the current checked-in product and the proposed extension, not on remembered wording.

### 10.1 Current implemented project

Calling the current application only CRUD plus a chatbot is too reductive. It has meaningful
software-engineering depth:

- a pure deterministic eligibility engine;
- conservative `unknown` propagation;
- immutable patient snapshots and approved trial versions;
- evidence-backed, reproducible criterion evaluations;
- transactional single and batch screening;
- reviewed document extraction with provenance;
- bounded, citation-validated explanation chat;
- ownership, degraded modes, evaluation fixtures, and browser workflows;
- a polished deployed frontend.

However, before the research extension it has limited ML research depth. The LLM is bounded
assistance around a deterministic product, not a trained or evaluated predictive model.

Honest current assessment:

| Dimension | Current score |
|---|---:|
| Product design and frontend | 8.0/10 |
| Full-stack/software engineering | 8.2/10 |
| Safety and explainability architecture | 8.5/10 |
| ML/research contribution | 4.5/10 |
| Dataset and empirical research depth | 4.0/10 |
| Overall BTech capstone | **7.4/10** |

The current project is already acceptable for a BTech final year, particularly as a software
engineering capstone. Its weakness is not lack of code; it is limited empirical research.

### 10.2 Planned scope is not earned credit

A document mentioning XGBoost, LightGBM, SHAP, MLflow, DBSCAN, FAISS, RAG, and local LLMs does
not increase the implemented-project score. If the extension is unfinished, weakly evaluated,
or visually disconnected, scope inflation can reduce the score.

An incoherent partial implementation could fall to roughly **6.5–7.0/10** because it would make
the product harder to run and the claims harder to defend.

### 10.3 Successfully completed extension

If R1–R8 are implemented with the declared gates, honest synthetic-data claims, strong
evaluation, and the planned frontend:

| Dimension | Possible completed score |
|---|---:|
| Product design and frontend | 9.0/10 |
| Full-stack/software engineering | 9.0/10 |
| Safety and explainability architecture | 9.0/10 |
| ML/research execution | 8.2/10 |
| Dataset and empirical research depth | 7.2/10 |
| Overall BTech capstone | **8.6–8.9/10** |

The ceiling remains below a clinically validated research system because the participant
dataset is synthetic and there is no prospective or external real-world validation. That is
acceptable for a BTech project when stated clearly.

The final extension would be above average in breadth and engineering complexity. The strongest
examiner story is not “many AI libraries.” It is:

> One carefully bounded platform demonstrates deterministic eligibility, synthetic predictive
> research, unsupervised cohort analytics, measured public-trial retrieval, grounded
> generation, reproducibility, and visible degraded modes without confusing those outputs.

## 11. Groq resilience and local LLM decision

### 11.1 Inspected hardware and deployment

Read-only inspection on 2026-07-26 found:

- Intel Core i3-7020U at 2.30 GHz;
- 2 physical cores / 4 threads;
- 7.7 GiB RAM, about 6.7 GiB available while idle;
- no supported GPU;
- Ollama 0.32.1 in Docker, bound to `127.0.0.1:11434`;
- `qwen2.5:1.5b`, approximately 986 MB;
- `llama3.2:1b`, approximately 1.3 GB;
- TrialSync backend, frontend, and PostgreSQL using little memory while idle.

This machine can fit either quantized model comfortably. CPU inference and semantic quality,
not RAM, are the primary constraints.

Ollama supports JSON-schema structured output, but its documentation still recommends schema
validation and temperature zero:
[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
Its concurrency documentation explains that requests may queue, parallel contexts increase
memory, and CPU inference defaults to limited parallelism:
[Ollama FAQ](https://docs.ollama.com/faq).

### 11.2 Measured benchmark

A bounded synthetic retrieval prompt contained:

- one recruiting type 2 diabetes record;
- one completed hypertension record;
- a request for relevant recruiting diabetes records;
- JSON-only output with NCT citations.

| Model | Cold total | Output speed | Observed semantic result |
|---|---:|---:|---|
| `qwen2.5:1.5b` | 28.0 s | 12.4 tokens/s | Incorrectly described/cited the completed hypertension record as relevant |
| `llama3.2:1b` | 24.6 s | 11.7 tokens/s | Also cited the irrelevant completed hypertension record |

A short, warm grounded explanation using Llama 3.2 completed in 8.1 seconds and answered the
substantive question correctly, but it failed the requested one-key JSON shape.

This was a smoke test, not a full provider evaluation. It is enough to reject an assumption that
either small model is automatically reliable for citation-sensitive RAG.

### 11.3 Capacity judgment

The current server can support:

- one short generation at a time;
- bounded 2K–4K context;
- approximately 50–150 output tokens;
- a patient user willing to wait roughly 6–15 seconds when the model is warm;
- occasional 20–30 second cold starts;
- a small request queue with explicit busy/timeout feedback.

It should not be expected to support:

- multiple simultaneous long RAG conversations;
- very long eligibility documents in one prompt;
- high-throughput public chatbot traffic;
- unvalidated structured extraction;
- automatic acceptance of citations or eligibility claims.

Qwen2.5 explicitly emphasizes improved structured-data and JSON behavior in its
[official Qwen2.5 announcement](https://qwenlm.github.io/blog/qwen2.5/), while Meta positions
Llama 3.2 1B for lightweight summarization and instruction following in its
[official Llama 3.2 announcement](https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/).
Those general capabilities do not override the observed application-specific failures.

### 11.4 Existing Groq behavior

TrialSync already has basic rate-limit handling:

- the structured client recognizes HTTP 429;
- it retries at most the configured bounded count;
- it maps exhausted retries to `PROVIDER_RATE_LIMITED`;
- document import falls back to deterministic extraction;
- explanation chat falls back to the canonical explainer.

The important weakness is that the current retry delay caps `Retry-After` to one second. That
is insufficient when Groq communicates a longer cooldown or when an account-level quota is
exhausted. Repeated users can also reach the provider independently before the application
learns that it should cool down.

### 11.5 Recommended 429-resilient provider gateway

Do not place Ollama in the default request path. Strengthen the Groq boundary:

```text
Request
  -> operation-specific cache lookup
  -> in-process concurrency semaphore
  -> shared provider cooldown/circuit check
  -> Groq call
       -> success: validate schema, citations, and scope
       -> 429: parse Retry-After, record cooldown, bounded retry only when short
       -> timeout/5xx: one jittered bounded retry
  -> deterministic fallback
```

Recommended behavior:

- keep the deterministic/manual product fully functional with no LLM;
- parse both numeric and HTTP-date `Retry-After` values;
- keep an in-memory `next_allowed_at` cooldown because production currently uses one backend
  process; avoid Redis or a queue;
- retry once only when the indicated wait is short and remains inside the request deadline;
- fall back immediately when the cooldown is long or the daily/token quota appears exhausted;
- add small randomized jitter to transient retry delays;
- limit concurrent Groq calls with an async semaphore;
- cache reviewed extraction by redacted source checksum + model + prompt version;
- cache public-trial RAG summaries by query/filter + corpus + retriever + model + prompt version;
- do not cross-user cache patient-specific chat answers;
- return an explicit rate-limited/degraded state and `retry_after_seconds` metadata;
- validate all NCT, criterion, evaluation, and evidence identifiers;
- reject unsupported generated claims;
- expose a user-controlled retry action after the cooldown;
- record only safe aggregate provider metrics, never prompt or patient content.

Operation-specific fallback remains:

- extraction: deterministic candidates and human review;
- screening explanation: canonical criterion explanations;
- RAG: deterministic ranked ClinicalTrials.gov results without generated comparison;
- eligibility: unchanged deterministic engine.

The local benchmark remains useful evidence for why this decision was made. Ollama can stay
deployed for other projects or future provider experiments, but it is not required by
TrialSync and should not be presented as an automatic answer to rate limiting.

## 12. Recommended frontend research area

The research extension should create a coherent visible surface:

### Research overview

- synthetic-data boundary;
- dataset and generator versions;
- champion model and evaluation summary;
- links to Scenario Lab, Cohort Atlas, Trial Discovery, and methods.

### Risk Scenario Lab

- selected synthetic participant;
- baseline dropout risk;
- missed-dose sweep and scenario trajectory;
- SHAP changes;
- threshold and calibration context;
- explicit model-sensitivity disclaimer.

### Cohort Atlas

- interactive cluster projection;
- DBSCAN cluster/noise summary;
- selected participant and FAISS neighbor edges;
- full-space similarity scores and feature differences;
- table alternative.

### Trial Discovery

- ClinicalTrials.gov filters and source date;
- ranked deterministic retrieval results;
- citation-validated bounded RAG comparison;
- provider-degraded state that preserves ranked results;
- send-to-review action.

### Methods and evidence

- dataset card;
- feature dictionary;
- leakage audit;
- model comparison and calibration;
- cluster stability;
- retrieval and grounding metrics;
- provider benchmark and limitations.

The frontend creates the first impression, but every visual must link back to the versioned
method or evidence that produced it.

## 13. Final go/no-go recommendation

### Go

- canonical PDF;
- GitHub Actions CI;
- separate multi-condition synthetic longitudinal dropout cohort;
- screening-derived patient-fact and screening-profile cohorts;
- logistic regression, XGBoost, LightGBM, MLflow, and SHAP;
- missed-dose Scenario Lab;
- DBSCAN and exact FAISS;
- Cohort Atlas;
- ClinicalTrials.gov retrieval with bounded, citation-validated RAG;
- rate-limit-aware Groq gateway and deterministic fallbacks;
- integrated evaluation and documentation.

### Do not do

- train dropout from screening rows;
- count 300 patient × trial screenings as 300 independent cohort members;
- use eligibility state as a dropout label;
- treat a what-if delta or SHAP value as causal;
- cluster on dropout outcome, predicted risk, or a single overall eligibility outcome;
- expose raw MLflow or Ollama publicly;
- automatically route 429s to an unevaluated 1B model;
- add automatic CD before migration, health-gate, and rollback behavior are stable;
- claim clinical validity from synthetic data.

### Next task

R0 has locked the condition portfolio, day-30/day-90 task, approximate prevalence, cohort
sizes, Scenario Lab direction, patient-fact and screening-profile representations, seeded PCA
display, and the Groq-resilience approach. Begin R1 only: generate a canonical screening PDF
from stored evidence and verify its populated, `unknown`, long-text, and pagination states.

Phase-specific details such as the exact synthetic event taxonomy, bounded generator regimes,
and concrete provider timeout values are implementation parameters to freeze and test inside
their authorized phases; they are not unresolved changes to the approved architecture.
