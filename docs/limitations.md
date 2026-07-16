# Limitations

- Synthetic data only; no real patient records, EHR integration, clinical validation, or compliance claim.
- The deterministic rule DSL supports a bounded subset of eligibility language. Unsupported language remains reviewable but evaluates as `unknown` until represented by a supported approved rule.
- Tesseract OCR is local, English-language, and best-effort. Handwriting, complex tables, poor scans, and recognition errors require human correction; OCR cannot approve a fact.
- Groq extraction and explanation are optional aids. They can time out, be rate-limited, or return invalid output; deterministic/manual workflows remain available. Provider output cannot decide eligibility.
- Conversation is limited to one stored screening, the latest ten messages, and evidence-grounded explanations. It cannot provide diagnosis, treatment, enrollment, or other medical advice.
- Batch screening is synchronous and intentionally bounded for the semester demo.
