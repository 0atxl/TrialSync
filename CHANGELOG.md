# Changelog

## Current status

- The deterministic screening workflow, evidence-backed reports, and CI are complete.
- R3's longitudinal dataset and R4's offline model comparison are accepted.
- LightGBM was selected by the original validation rule; XGBoost (`xgboost-05`) is the user-selected R5 runtime model.
- The R6 V3 cohort backend, read-only APIs, and exact FAISS indexes are complete. Its coordinated R5/R6 frontend remains pending.
- Remaining roadmap work: the R5 risk backend, coordinated R5/R6 frontend, eligibility-criteria RAG (R7), and integrated evaluation/delivery (R8).

## Milestones

- Completed the immutable, deterministic patient–trial screening workflow with batch screening, reviewed import, grounded explanations, and canonical reports.
- Accepted the R3 data contract, frozen artifacts, linkage and leakage checks, and reproducibility metadata.
- Completed the R4 comparison, uncertainty analysis, SHAP evidence, and MLflow record; retained the user’s XGBoost runtime decision separately from the historical LightGBM validation selection.
- Approved the sealed R6 V3 controlled cohort after DBSCAN, exact-index, neighbor-relevance, runtime-readability, and artifact-seal review. Earlier R6 experiments are retired provenance only.
