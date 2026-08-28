# Evaluation

TrialSync evaluates both the reliability of its evidence-backed patient–trial matching core and, as the research extension is implemented, the reproducibility of its dropout-risk, cohort, and retrieval components. The safeguards tested here are what make the combined workflow inspectable and credible.

The extension gate will also reconcile trial-grouped screening totals with versioned enrollment
links and risk predictions, verify complete-criteria expansion before every Gemini summary, and
retain GitHub Actions CI evidence for the tested commit. Deployment remains a manual,
health-checked Compose procedure until automated CD is needed.
The dropout-data gate verifies generator provenance, preservation of the exact Data Designer
configuration and run artifacts, label independence from LLM-generated fields, and leakage-safe
day-30/day-90 splits. Data Designer 0.8.0 executes the current sampler-and-expression recipe on the
local CPU: generation makes no hosted model requests and requires no NVIDIA credentials. A frozen
Parquet artifact can also be trained and evaluated offline. Byte-identical regeneration is not
claimed because Data Designer 0.8.0 does not expose a project-level sampler seed.
If NCT02054715-D1 participant rows become legitimately accessible, they receive a separate
study-specific protocol and report; their metrics are never pooled with the public synthetic
cohort. The currently public dictionary and aggregate paper are not row-level validation data.

Run the reproducible offline evaluation with `make evaluate`; detailed fixture measurements are in [PHASE7_EVALUATION.md](../backend/evaluation/PHASE7_EVALUATION.md) and [PHASE8_EVALUATION.md](../backend/evaluation/PHASE8_EVALUATION.md). All fixtures and seeded records are synthetic.

The held-out fixture checks candidate precision/recall, exact structure, source-quote validity, supported-conversation citation validity, refusal behavior, and deterministic parser latency. The six-workflow browser suite covers registration/history, needs-review evidence, batch screening, reviewed import, conversation persistence/refusal, and responsive chatbot interaction. Backend tests cover the rule engine, ownership, persistence, provider failures, and OCR fallback/provenance.

The R3 smoke artifact contains 20 enrollments and 4 synthetic dropouts (20%). The demo artifact
contains 400 enrollments and 64 synthetic dropouts (16%). The experiment artifact contains 4,000
enrollments and 702 synthetic dropouts (17.55%): 491/2,800 in training, 105/600 in validation, and
106/600 in test. Its schema, linkage, chronology, censoring, relationship, split, and leakage
checks pass. These values are generated-label prevalence, not model accuracy, prediction
performance, a forced target, or a clinical estimate.

R4 used the frozen 2,800/600/600 participant-level split to compare dummy, logistic-regression,
XGBoost, and LightGBM classifiers. The original validation rule selected LightGBM; historical XGBoost (`xgboost-05`)
was the strongest observed frozen-test comparator in that original comparison and the initial R5 runtime/product model.
For historical `xgboost-05`, the observed test metrics were AUROC 0.6807, AUPRC 0.3617, Brier
0.1331, precision 0.3418, recall 0.5094, specificity 0.7895, and F1 0.4091.
The active research runtime is the separately reviewed `xgboost-06` package (`dropout-xgboost-06-v1`),
which was not part of the original R4 comparison and was later user-selected for directional realism, not validation-selected.
Research risk models do not alter deterministic eligibility. In the original R4 comparison, both tree models (`xgboost-05` and `lightgbm-05`)
received 1,000-repeat bootstrap uncertainty estimates and global/local SHAP analysis. See
[the R4 experiment report](r4-dropout-model-experiment.md) for the full protocol, comparison, and
limitations.

The 2026-08-14 local verification gate reports 173 backend tests, including 13 focused R3 tests
with 88.22% generator coverage, plus 72 frontend tests, a successful frontend production build,
Ruff, strict mypy, ESLint, TypeScript, migrations, Compose validation, and the held-out synthetic
evaluation. The 4,000-row review candidate also passes the frozen schema, foreign-key, immutable
snapshot, chronology, censoring, participant-split, and leakage checks. These counts are software
and synthetic-data verification results, not clinical performance claims. The R4 model metrics are
also synthetic-task results and do not establish clinical validity.

R2 adds `.github/workflows/ci.yml`, which reproduces the verification gate on a clean GitHub
Actions runner with PostgreSQL and builds both application images without provider credentials.
Automated deployment and rollback are intentionally outside the current CI scope.

These are software, fixture, and synthetic-model checks, not clinical validation. Live Groq
measurements require a separately documented run with only synthetic data. OCR output is evaluated
as reviewable source text, not as eligibility evidence or confidence.
