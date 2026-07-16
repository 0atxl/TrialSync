# Evaluation

Run the reproducible offline evaluation with `make evaluate`; detailed fixture measurements are in [PHASE7_EVALUATION.md](../backend/evaluation/PHASE7_EVALUATION.md) and [PHASE8_EVALUATION.md](../backend/evaluation/PHASE8_EVALUATION.md). All fixtures and seeded records are synthetic.

The held-out fixture checks candidate precision/recall, exact structure, source-quote validity, supported-conversation citation validity, refusal behavior, and deterministic parser latency. The browser suite covers registration through history, needs-review, batch screening, reviewed import, and conversation persistence/refusal. Backend tests cover the rule engine, ownership, persistence, provider failures, and OCR fallback/provenance.

These are software and fixture checks, not a clinical validation or trained-model evaluation. Live Groq measurements require a separately documented run with only synthetic data. OCR output is evaluated as reviewable source text, not as eligibility evidence or confidence.
