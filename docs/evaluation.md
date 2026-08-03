# Evaluation

TrialSync evaluates both the reliability of its evidence-backed patient–trial matching core and, as the research extension is implemented, the reproducibility of its dropout-risk, cohort, and retrieval components. The safeguards tested here are what make the combined workflow inspectable and credible.

The extension gate will also reconcile trial-grouped screening totals with versioned enrollment
links and risk predictions, verify complete-criteria expansion before every Gemini summary, and
retain GitHub Actions CI evidence for the tested commit. Deployment remains a manual,
health-checked Compose procedure until automated CD is needed.
The dropout gate will verify generator provenance, offline reproducibility without NVIDIA
credentials, label independence from LLM-generated fields, and leakage-safe day-30/day-90 splits.
If NCT02054715-D1 participant rows become legitimately accessible, they receive a separate
study-specific protocol and report; their metrics are never pooled with the public synthetic
cohort. The currently public dictionary and aggregate paper are not row-level validation data.

Run the reproducible offline evaluation with `make evaluate`; detailed fixture measurements are in [PHASE7_EVALUATION.md](../backend/evaluation/PHASE7_EVALUATION.md) and [PHASE8_EVALUATION.md](../backend/evaluation/PHASE8_EVALUATION.md). All fixtures and seeded records are synthetic.

The held-out fixture checks candidate precision/recall, exact structure, source-quote validity, supported-conversation citation validity, refusal behavior, and deterministic parser latency. The six-workflow browser suite covers registration/history, needs-review evidence, batch screening, reviewed import, conversation persistence/refusal, and responsive chatbot interaction. Backend tests cover the rule engine, ownership, persistence, provider failures, and OCR fallback/provenance.

The 2026-08-04 local verification gate reports 159 backend tests, 72 frontend tests,
6 browser end-to-end workflows, a successful frontend production build, Ruff,
mypy, ESLint, TypeScript, migrations, the canonical screening-report API/UI tests,
and the held-out synthetic evaluation. The R1 visual review covered desktop and
narrow screening details plus a three-page generated PDF.
These counts are software verification results, not clinical performance claims.

R2 adds `.github/workflows/ci.yml`, which reproduces the verification gate on a clean GitHub
Actions runner with PostgreSQL and builds both application images without provider credentials.
Automated deployment and rollback are intentionally outside the current CI scope.

These are software and fixture checks, not a clinical validation or trained-model evaluation. Live Groq measurements require a separately documented run with only synthetic data. OCR output is evaluated as reviewable source text, not as eligibility evidence or confidence.
