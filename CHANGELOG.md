# Changelog

## Current status

- The deterministic screening workflow, evidence-backed reports, and CI are complete.
- R3's longitudinal dataset and R4's offline model comparison are accepted.
- LightGBM was selected by the original validation rule; XGBoost (`xgboost-05`) is the user-selected R5 runtime model.
- The R5 backend packages and verifies `xgboost-05` without retraining and uses platform-owned
  enrollments, append-only dose/visit/measurement/adverse-event records, immutable day-30 snapshots,
  and source-preserved predictions.
- The R6 V3 backend projects saved screenings into the frozen patient-fact and screening-profile
  spaces for out-of-sample DBSCAN context and exact FAISS queries.
- Remaining roadmap work: regenerate and activate the extended V3 artifact, build the coordinated but
  independently selectable frontend tools, eligibility-criteria RAG (R7), and integrated
  evaluation/delivery (R8).

## Milestones

- Completed the immutable, deterministic patient–trial screening workflow with batch screening, reviewed import, grounded explanations, and canonical reports.
- Accepted the R3 data contract, frozen artifacts, linkage and leakage checks, and reproducibility metadata.
- Completed the R4 comparison, uncertainty analysis, SHAP evidence, and MLflow record; retained the user’s XGBoost runtime decision separately from the historical LightGBM validation selection.
- Implemented the initial R5 checksum-verified CPU XGBoost package, immutable prediction,
  day-30 feature validation, native Tree SHAP inference, authenticated API foundation, and focused
  backend tests; approved its enrollment/event integration revision before finalizing persistence.
- Approved the sealed R6 V3 controlled cohort after DBSCAN, exact-index, neighbor-relevance, runtime-readability, and artifact-seal review. Earlier R6 experiments are retired provenance only.
- Implemented the shared ingestion-to-research integration contract covering independent dropout,
  cohort, and similarity actions from one authorized saved screening.
