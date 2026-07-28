# Evaluation

TrialSync evaluates both the reliability of its evidence-backed patient–trial matching core and, as the research extension is implemented, the reproducibility of its dropout-risk, cohort, and retrieval components. The safeguards tested here are what make the combined workflow inspectable and credible.

The extension gate will also reconcile trial-grouped screening totals with versioned enrollment
links and risk predictions, verify complete-criteria expansion before every Gemini summary, and
retain GitHub Actions evidence for the tested commit, deployment health gate, and rollback path.

Run the reproducible offline evaluation with `make evaluate`; detailed fixture measurements are in [PHASE7_EVALUATION.md](../backend/evaluation/PHASE7_EVALUATION.md) and [PHASE8_EVALUATION.md](../backend/evaluation/PHASE8_EVALUATION.md). All fixtures and seeded records are synthetic.

The held-out fixture checks candidate precision/recall, exact structure, source-quote validity, supported-conversation citation validity, refusal behavior, and deterministic parser latency. The six-workflow browser suite covers registration/history, needs-review evidence, batch screening, reviewed import, conversation persistence/refusal, and responsive chatbot interaction. Backend tests cover the rule engine, ownership, persistence, provider failures, and OCR fallback/provenance.

The latest local verification gate reports 95 backend tests, 38 frontend tests,
6 browser end-to-end workflows, a successful frontend production build, Ruff,
mypy, ESLint, TypeScript, migrations, and the held-out synthetic evaluation.
These counts are software verification results, not clinical performance claims.

These are software and fixture checks, not a clinical validation or trained-model evaluation. Live Groq measurements require a separately documented run with only synthetic data. OCR output is evaluated as reviewable source text, not as eligibility evidence or confidence.
