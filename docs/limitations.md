# Scope and reliability boundaries

These boundaries keep TrialSync’s current patient matching workflow and planned dropout-risk research interpretable and reproducible rather than reducing the project to generic automation.

- Public repository, tests, screenshots, and demo data are synthetic only; no EHR integration,
  clinical validation, or compliance claim.
- NeMo Data Designer generation does not make generated outcomes empirical evidence. A reviewed
  uniform sampler draw and dependent expression produce the probabilistic synthetic label locally,
  while TrialSync owns relational linkage, censoring, participant-level splits, leakage-safe views,
  and validation. No LLM field determines the label, no hosted model request is made, and no
  duplicate offline simulator is maintained.
- The 400-enrollment demo has 64 generated dropouts (16%); the 4,000-enrollment experiment has
  702 (17.55%). These are observed stochastic cohort statistics—not prediction accuracy, forced
  targets, clinical estimates, or evidence that a future model will generalize to real participants.
- The physical Parquet files are intentionally not fully normalized: each enrollment preserves an
  immutable copy of the participant baseline fields. The contract validates those copies and uses
  `site_region`; it does not export `site_id`.
- NCT02054715-D1 is study-specific, and its public dictionary and aggregate paper do not include
  participant rows. Unless the rows become legitimately accessible and a separate evaluation is
  completed, it is a future adapter rather than evidence for TrialSync. NCT-inspired synthetic
  rows must not be counted as additional real participants.
- Planned dropout-risk outputs will be versioned fixed-horizon research predictions. They will not
  be eligibility scores or alter deterministic patient–trial matching.
- Planned trial-level dropout charts will cover only potentially eligible demo enrollments with an explicit
  versioned screening/enrollment/prediction linkage; linked and unlinked denominators must be shown.
- The planned RAG workflow will use LangChain to rank candidate trials, expand each bounded
  candidate to its complete approved criteria set, and use Gemini for the structured summary.
  Ranked candidates will remain available when generation is unavailable.
- The deterministic rule DSL supports a bounded subset of eligibility language. Unsupported language remains reviewable but evaluates as `unknown` until represented by a supported approved rule.
- Tesseract OCR is local, English-language, and best-effort. Handwriting, complex tables, poor scans, and recognition errors require human correction; OCR cannot approve a fact.
- Groq extraction and explanation are optional aids. They can time out, be rate-limited, or return invalid output; deterministic/manual workflows remain available. Provider output cannot decide eligibility.
- Conversation is limited to one stored screening, the latest ten messages, and evidence-grounded explanations. It cannot provide diagnosis, treatment, enrollment, or other medical advice. Responses are intentionally non-streaming; the UI shows a bounded typing state while the validated response is generated.
- Operational chat metrics are written to privacy-safe application logs only; they are not a persisted analytics or audit dataset and exclude question/document text and provider payloads.
- Batch screening is synchronous and intentionally bounded for the semester demo.
