# R4 dropout-model experiment

## Outcome

R4 is complete for the synthetic multi-condition Track A experiment. The frozen day-30 landmark
dataset was used to compare a dummy baseline, logistic regression, XGBoost, and LightGBM. The
experiment includes validation-based model selection, held-out test evaluation, calibration,
threshold metrics, 1,000-repeat bootstrap uncertainty, SHAP explanations, reproducibility checks,
and local MLflow tracking.

This is a BTech research demonstration over generated data. Its probabilities are model outputs
for the documented synthetic task, not clinically calibrated real-world risks.

## Frozen experiment contract

| Item | Value |
|---|---|
| Experiment | `r4-kaggle-track-a-v1` |
| Input | `landmark_day30_features.parquet` |
| Question | Using information available through day 30, predict dropout during days 31–90 |
| Dataset | 4,000 synthetic enrollments; 702 dropouts (17.55%) |
| Split | 2,800 train / 600 validation / 600 test, frozen at participant level |
| Test events | 106 of 600 (17.67%) |
| Dataset contract | `r3-dataset-contract-v1` |
| Feature schema | `r4-day30-features-v1` |
| Random seed | 42 |
| Selection rule | Validation AUPRC, then validation Brier score |
| Threshold rule | Maximum validation F1, stored per candidate |

The validation split selected candidates and thresholds. The test split was opened only for final
evaluation; its results were not used to rewrite the selection rule.

## Model comparison

| Model | Test AUROC | Test AUPRC | Brier | Log loss | Precision | Recall | Specificity | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dummy | 0.5000 | 0.1767 | 0.1455 | 0.4663 | 0.1767 | 1.0000 | 0.0000 | 0.3003 |
| Logistic regression | 0.6445 | 0.3056 | 0.2273 | 0.6481 | 0.2575 | 0.5660 | 0.6498 | 0.3540 |
| LightGBM (`lightgbm-04`) | 0.6607 | 0.3268 | 0.1367 | 0.4438 | 0.2886 | 0.5472 | 0.7105 | 0.3779 |
| XGBoost (`xgboost-05`) | **0.6807** | **0.3617** | **0.1331** | **0.4311** | **0.3418** | 0.5094 | **0.7895** | **0.4091** |

The dummy model predicts the training prevalence for every row. It is not a regression model and
does not learn feature relationships; it establishes the minimum baseline that a useful classifier
must beat.

## Historical selection and product decision

The original frozen validation rule selected LightGBM. Its validation AUPRC was 0.342054, narrowly
above XGBoost's 0.341860, so that historical rule chose `lightgbm-04`; its stored threshold is
0.171399.

XGBoost produced the strongest observed frozen-test results and has been selected by the project
owner as the R5 runtime/product model (`xgboost-05`). Its stored threshold is 0.213477. This is a
later product decision informed by the comparison; it does not rewrite the original validation
selection or make XGBoost validation-selected.

The two tree models are practically close. The experiment supports a moderate synthetic signal,
not a claim that either model is clinically strong.

## Bootstrap uncertainty

The held-out test set was resampled with replacement 1,000 times. This estimates how much the
reported metrics could vary because the test set is finite.

| Model | Metric | Estimate | 95% interval |
|---|---|---:|---:|
| LightGBM | AUROC | 0.6607 | 0.5995–0.7153 |
| LightGBM | AUPRC | 0.3268 | 0.2583–0.4288 |
| LightGBM | Brier | 0.1367 | 0.1176–0.1561 |
| XGBoost | AUROC | 0.6807 | 0.6194–0.7354 |
| XGBoost | AUPRC | 0.3617 | 0.2870–0.4686 |
| XGBoost | Brier | 0.1331 | 0.1146–0.1519 |

The intervals overlap substantially, so the observed XGBoost advantage is not evidence of a
decisive separation between the models.

## SHAP findings

Global and local SHAP analyses were completed for LightGBM and XGBoost. The leading global signals
were logically aligned with the generator contract, including missed-dose rate, functional
severity, missed-visit rate, treatment burden, travel/access burden, patient-reported burden, and
support availability. The exact ordering differs slightly between models.

SHAP explains how a fitted model used its inputs. It does not prove that any feature caused
dropout. Raw-output reconciliation errors were within library tolerance:

- LightGBM: `5.329070518200751e-15`.
- XGBoost: `1.430511474609375e-06`.

## Reproducibility and MLflow

The final metadata records the dataset checksum, schema fingerprints, generator and split
versions, code commit, dependency versions, seed, thresholds, selected candidate, and intended and
prohibited uses. Reloaded predictions matched with a maximum probability difference of `0.0`.

The historical LightGBM pipeline is registered locally as:

- model: `trialsync_dropout_track_a`;
- version: `2`;
- alias: `champion` (historical experiment alias; not the R5 runtime model);
- run: `6e1fa44c84994c7f90ffb1b9756669fa`.

Model binaries, the SQLite MLflow store, and the complete Kaggle output bundle remain local/ignored
artifacts rather than Git-tracked application assets. R5 must explicitly package, checksum, and
accept the runtime model before exposing inference.

## R5 handoff

Dropout prediction will be integrated into the existing saved-screening workspace. Screening data
prefills baseline fields, while required day-30 follow-up values are loaded from a linked research
enrollment or requested explicitly. Missing values are never converted to zero. The result displays
probability, threshold, day-90 horizon, model version, and bounded SHAP contributions beside the
unchanged deterministic eligibility result.

R5 will package XGBoost `xgboost-05` as the runtime model. The historical LightGBM validation
selection and XGBoost frozen-test comparison remain visible for provenance.
