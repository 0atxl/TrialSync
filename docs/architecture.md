# TrialSync architecture

TrialSync is a controlled research system for **Clinical Trial Patient Matching and Dropout Prediction**. Its current operational core is explainable patient–trial matching. The R3 dataset and R4 offline model evaluation are complete. R5 platform enrollment/event/model-serving and R6 saved-screening projection/artifact-serving bridges are integrated into the saved-screening frontend, with linked population-wide Recruitment Overview and Cohort Atlas routes. RAG over approved trial eligibility criteria remains future work.

```text
reviewed text/PDF -> deterministic text extraction -> optional local Tesseract OCR
                         -> Groq candidate extraction (default when configured)
                         -> human review/approval -> structured records
structured records -> immutable patient snapshot + approved trial version
                   -> deterministic rule engine -> stored criterion evidence/result
stored screening + authoritative evidence -> canonical PDF report
stored screening + authoritative evidence -> bounded explanation conversation
stored screening -> platform-owned research enrollment
                 -> append-only dose / visit / measurement / adverse-event records
                 -> immutable sourced day-30 feature snapshot
                   -> checksum-verified XGBoost inference + Tree SHAP
                   -> immutable research prediction + trial overview API
750 versioned patient snapshots × 20 approved trial versions
                   -> 15,000 pure deterministic evaluations
                   -> patient-fact + screening-profile representations
                   -> DBSCAN reports + exact FAISS indexes -> read-only research APIs
stored screening -> frozen R6 feature projection
                 -> out-of-sample cluster association and exact reference-neighbor query
stored screening detail -> independently open retention risk, cohort context, or similar participants
research workspace -> trial-level screening/prediction reconciliation + sealed-cohort Atlas
```

The implemented R3 longitudinal generator uses the NVIDIA Data Designer 0.8.0 Python package
locally. Statistical sampler and expression columns create the synthetic fields; the accepted
recipe makes zero hosted model requests and requires no NVIDIA API key. TrialSync supplies
relational linkage and schedules, then owns censoring, participant-level splits, leakage-safe
views, and validation. A uniform sampler draw and reviewed expression produce the probabilistic
synthetic outcome; there is no duplicate offline simulator and no LLM-generated label.

```text
Data Designer samplers/expressions (local CPU)
  -> seven linked source tables
     participants -> enrollments -> doses / visits / measurements / adverse events -> outcomes
  -> TrialSync linkage, chronology, censoring, split, and leakage validation
  -> landmark_day30_features + dynamic_landmarks + survival_features
  -> completed R4 model comparison, calibration, bootstrap uncertainty, SHAP, and MLflow record
```

The physical enrollment table intentionally copies the participant baseline fields as an immutable
enrollment snapshot; the files are therefore relational but not fully normalized. `site_region` is
the frozen site-context field. New generations record a run ID, UTC timestamp, contract version,
schema fingerprint, and per-column provenance. The public NCT02054715-D1 schema may inform a future
adapter; a row-level benchmark runs only if participant data becomes legitimately accessible and
never becomes a runtime dependency. All research outputs remain separate from deterministic
eligibility.

The FastAPI application owns authentication, owner-scoped persistence, document review, immutable screening history, and provider-free canonical PDF assembly. PostgreSQL schema changes are versioned with Alembic. The React/Vite client consumes only the versioned HTTP API.

The Overview uses a derived, owner-scoped `GET /api/v1/overview` aggregate rather than loading full
screening records into the landing page. It returns complete eligibility counts, a bounded 56-day
activity series, dropout follow-up states for potentially eligible screenings, attention items, and
recent screening summaries. No dashboard state is persisted. Research artifact validation can mark
the dropout summary as degraded without withholding eligibility, activity, or screening links.

The domain engine is deliberately isolated from FastAPI, SQLAlchemy, provider clients, system time, and OCR. It evaluates typed facts and approved rule JSON only. Missing, stale, conflicting, unsupported, and unit-incompatible information stays `unknown`; a provider cannot approve data or change the final state.

Imports are bounded to 1 MB of pasted text or 5 MB/10 PDF pages. PDFs first use embedded text. If that is insufficient, local Tesseract OCR runs after Poppler rasterization at 200 DPI with timeouts. OCR source text remains page-local, is marked in the review UI, and is never trusted without human approval. Groq receives only the bounded synthetic source text and must return schema-validated candidates with exact, verified quotations. Provider failure falls back to deterministic candidates.

The screening conversation is scoped to one authorized saved screening. The server rebuilds authoritative context each request, validates citations, persists at most ten messages, and rejects unsupported, advice, cross-record, and prompt-injection requests. Conversation content is never evidence.

## Final request flow

The React client authenticates once, then sends only the current user action to
the versioned FastAPI API. A screening-detail request loads the immutable patient
snapshot, approved trial version, stored criterion evaluations, evidence, missing
information, and the latest bounded chat messages. The chat endpoint authorizes
the screening through the authenticated owner, assembles that context on the
server, and returns a validated answer with criterion/evidence citations and
replacement suggestions. The browser renders the persisted user question and
assistant answer in an internally scrolling transcript; it never supplies
authoritative history or screening state to the provider.

The dropout workflow begins from that same saved-screening context rather than from a disconnected
training record. The frontend exposes **Start research follow-up** and, once the day-30 snapshot is
ready, **Predict dropout risk**. TrialSync resolves the immutable snapshot, approved trial version,
screening, and platform-owned research enrollment. Baseline fields are prefilled from that context.
Required day-30 adherence, visit, adverse-event, and updated-severity fields are derived from linked,
append-only research events or requested in the same panel.
Unavailable follow-up values remain missing and are never silently interpreted as zero. The
accepted versioned research API validates the resulting feature snapshot and returns probability, threshold,
horizon, model version, and SHAP contributions for display beside the unchanged eligibility result.

The same saved screening independently exposes **View cohort context** and **Find similar
participants**. The server projects its immutable facts and deterministic evidence pattern through
the active R6 run's frozen transforms. The patient is an out-of-sample overlay on the sealed
reference landscape: it does not mutate the 750 reference members, DBSCAN clusters, or FAISS
indexes. DBSCAN association, FAISS neighbors, and dropout prediction are separate requests and
never consume one another's output. The authoritative identity, longitudinal-event, projection,
API, and acceptance boundaries are defined in
[`research-integration-contract.md`](research-integration-contract.md).

The deterministic matching boundary is deliberate: parsing and approved rule
evaluation produce the eligibility outcome, and persistence stores the
reproducible evidence-backed result. The dropout model is separately versioned and
evaluated independently, allowing TrialSync to expose a forward-looking retention
signal without turning a risk score into a match decision. Groq may propose
reviewable import candidates or provide an AI explanation of a stored result,
but it cannot approve candidates, create evidence, change a criterion result, or
access another record. Provider-disabled, timeout, rate-limit, invalid-output,
and refusal paths use canonical server explanations or safe refusal responses.
The saved-screening `report.pdf` endpoint assembles only the authorized immutable
screening, snapshot, approved trial version, stored evaluations, and version
metadata; it never calls a provider or recalculates eligibility. The browser keeps
the same evidence visible alongside the download action.
Operational chat metrics contain provider/model, prompt version, latency,
validation outcome, answer state, and citation count; they exclude questions,
documents, raw payloads, and secrets.
