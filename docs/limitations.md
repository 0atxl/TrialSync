# Scope and reliability boundaries

These boundaries keep TrialSync’s current patient matching workflow and planned dropout-risk research interpretable and reproducible rather than reducing the project to generic automation.

- Synthetic data only; no real patient records, EHR integration, clinical validation, or compliance claim.
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
