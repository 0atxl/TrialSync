"""Train the R4 v2 adherence-aware XGBoost model with monotonic constraints.

This script can be run locally or pasted into a Kaggle notebook.
It:
1. Loads landmark_day30_features.parquet (and computes streaks if dose/visit parquets exist)
2. Uses the v2 feature schema (including scheduled/missed counts and streaks)
3. Fits an XGBClassifier with strict monotonic constraints on adherence & burden features
4. Evaluates test AUROC, AUPRC, Brier score, F1
5. Runs scenario acceptance checks (0/8 < 2/8 < 3/8 < 4/8 < 8/8, streaks, counts)
6. Exports models/xgboost_pipeline.joblib, feature_schema.json, and input_example.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

CATEGORICAL_FEATURES = ["condition_category", "site_region", "treatment_arm", "sex"]

NUMERIC_FEATURES = [
    "age",
    "baseline_functional_severity",
    "patient_reported_burden",
    "baseline_comorbidity_burden",
    "baseline_treatment_burden",
    "travel_access_burden",
    "support_availability",
    "medication_count",
    "latest_functional_severity",
    "functional_severity_slope",
    "functional_observation_count",
    "scheduled_dose_count",
    "missed_dose_count",
    "missed_dose_rate",
    "longest_missed_dose_streak",
    "delayed_visit_count",
    "missed_visit_count",
    "missed_visit_rate",
    "longest_missed_visit_streak",
    "mean_visit_delay_days",
    "measurement_missingness_rate",
    "adverse_event_count",
    "adverse_event_burden",
]

ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def validate_streak_features(df: pd.DataFrame) -> None:
    """Validate explicit streak and count columns in training data."""
    required_cols = [
        "longest_missed_dose_streak",
        "longest_missed_visit_streak",
        "scheduled_dose_count",
        "missed_dose_count",
        "scheduled_visit_count",
        "missed_visit_count",
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required training column(s): {', '.join(missing)}. "
            "Training requires explicit streak features or event-level parquet sources."
        )

    for col in required_cols:
        series = df[col]
        if series.isna().any():
            raise ValueError(f"Column '{col}' contains null/missing values.")
        if not np.issubdtype(series.dtype, np.integer) and not (series == series.round()).all():
            raise ValueError(f"Column '{col}' must contain integer values.")
        if (series < 0).any():
            raise ValueError(f"Column '{col}' contains negative values.")

    # Validate missed count <= scheduled count
    if (df["missed_dose_count"] > df["scheduled_dose_count"]).any():
        raise ValueError("missed_dose_count exceeds scheduled_dose_count in training data.")
    if (df["missed_visit_count"] > df["scheduled_visit_count"]).any():
        raise ValueError("missed_visit_count exceeds scheduled_visit_count in training data.")

    # Validate zero misses require zero streak
    if ((df["missed_dose_count"] == 0) & (df["longest_missed_dose_streak"] != 0)).any():
        raise ValueError("longest_missed_dose_streak must be 0 when missed_dose_count is 0.")
    if ((df["missed_visit_count"] == 0) & (df["longest_missed_visit_streak"] != 0)).any():
        raise ValueError("longest_missed_visit_streak must be 0 when missed_visit_count is 0.")

    # Validate positive misses require streak >= 1
    if ((df["missed_dose_count"] > 0) & (df["longest_missed_dose_streak"] < 1)).any():
        raise ValueError(
            "longest_missed_dose_streak must be at least 1 when missed_dose_count > 0."
        )
    if ((df["missed_visit_count"] > 0) & (df["longest_missed_visit_streak"] < 1)).any():
        raise ValueError(
            "longest_missed_visit_streak must be at least 1 when missed_visit_count > 0."
        )

    # Validate streak <= missed count
    if (df["longest_missed_dose_streak"] > df["missed_dose_count"]).any():
        raise ValueError("longest_missed_dose_streak exceeds missed_dose_count in training data.")
    if (df["longest_missed_visit_streak"] > df["missed_visit_count"]).any():
        raise ValueError("longest_missed_visit_streak exceeds missed_visit_count in training data.")


def compute_streaks_if_needed(
    data_dir: Path,
    landmarks: pd.DataFrame,
) -> pd.DataFrame:
    """Derive streak features from dose and visit event tables if not already present."""
    df = landmarks.copy()

    dose_path = data_dir / "research_dose_events.parquet"
    if "longest_missed_dose_streak" not in df.columns and dose_path.exists():
        print("Computing longest_missed_dose_streak from dose events...")
        doses = pd.read_parquet(dose_path)
        doses_30 = doses[doses["event_day"] <= 30]

        def _calc_dose_streak(group: pd.DataFrame) -> int:
            sorted_g = group.sort_values("event_day")
            longest = current = 0
            for missed in sorted_g["missed_count"]:
                if missed > 0:
                    current += 1
                    if current > longest:
                        longest = current
                else:
                    current = 0
            return longest

        if doses_30.empty:
            dose_streaks = pd.DataFrame(
                {
                    "research_enrollment_id": pd.Series(dtype=str),
                    "longest_missed_dose_streak": pd.Series(dtype=int),
                }
            )
        else:
            dose_streaks = (
                doses_30.groupby("research_enrollment_id")
                .apply(_calc_dose_streak, include_groups=False)
                .reset_index(name="longest_missed_dose_streak")
            )
        df = df.merge(dose_streaks, on="research_enrollment_id", how="left")
        missing_history = df["longest_missed_dose_streak"].isna() & (df["missed_dose_count"] > 0)
        if missing_history.any():
            missing_count = int(missing_history.sum())
            raise ValueError(
                f"Cannot derive longest_missed_dose_streak: {missing_count} enrollment(s) with "
                "positive missed doses lack dose event history."
            )
        df["longest_missed_dose_streak"] = df["longest_missed_dose_streak"].fillna(0).astype(int)

    visit_path = data_dir / "research_visit_events.parquet"
    if "longest_missed_visit_streak" not in df.columns and visit_path.exists():
        print("Computing longest_missed_visit_streak from visit events...")
        visits = pd.read_parquet(visit_path)
        visits_30 = visits[visits["event_day"] <= 30]

        def _calc_visit_streak(group: pd.DataFrame) -> int:
            sorted_g = group.sort_values("event_day")
            longest = current = 0
            for status in sorted_g["visit_status"]:
                if status == "missed":
                    current += 1
                    if current > longest:
                        longest = current
                else:
                    current = 0
            return longest

        if visits_30.empty:
            visit_streaks = pd.DataFrame(
                {
                    "research_enrollment_id": pd.Series(dtype=str),
                    "longest_missed_visit_streak": pd.Series(dtype=int),
                }
            )
        else:
            visit_streaks = (
                visits_30.groupby("research_enrollment_id")
                .apply(_calc_visit_streak, include_groups=False)
                .reset_index(name="longest_missed_visit_streak")
            )
        df = df.merge(visit_streaks, on="research_enrollment_id", how="left")
        missing_history = df["longest_missed_visit_streak"].isna() & (df["missed_visit_count"] > 0)
        if missing_history.any():
            missing_count = int(missing_history.sum())
            raise ValueError(
                f"Cannot derive longest_missed_visit_streak: {missing_count} enrollment(s) with "
                "positive missed visits lack visit event history."
            )
        df["longest_missed_visit_streak"] = df["longest_missed_visit_streak"].fillna(0).astype(int)

    validate_streak_features(df)
    return df


def build_pipeline(
    cat_columns: list[str], num_columns: list[str]
) -> tuple[Pipeline, tuple[int, ...]]:
    """Construct a pipeline with exact directional constraints."""
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(sparse_output=False, handle_unknown="ignore"), cat_columns),
            ("num", StandardScaler(), num_columns),
        ]
    )

    numeric_constraints = {
        "age": 0,
        "baseline_functional_severity": 1,
        "patient_reported_burden": 1,
        "baseline_comorbidity_burden": 1,
        "baseline_treatment_burden": 1,
        "travel_access_burden": 1,
        "support_availability": -1,
        "medication_count": 0,
        "latest_functional_severity": 1,
        "functional_severity_slope": 1,
        "functional_observation_count": 0,
        "scheduled_dose_count": 0,
        "missed_dose_count": 1,
        "missed_dose_rate": 1,
        "longest_missed_dose_streak": 1,
        "delayed_visit_count": 1,
        "missed_visit_count": 1,
        "missed_visit_rate": 1,
        "longest_missed_visit_streak": 1,
        "mean_visit_delay_days": 1,
        "measurement_missingness_rate": 1,
        "adverse_event_count": 1,
        "adverse_event_burden": 1,
    }

    return preprocessor, tuple(numeric_constraints[name] for name in num_columns)


def train_and_evaluate(
    data_dir: Path,
    output_dir: Path,
    random_state: int = 42,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    landmarks_path = data_dir / "landmark_day30_features.parquet"
    landmarks = pd.read_parquet(landmarks_path)
    df = compute_streaks_if_needed(data_dir, landmarks)

    train = df[df["dataset_split"] == "train"].copy()
    val = df[df["dataset_split"] == "validation"].copy()
    test = df[df["dataset_split"] == "test"].copy()

    X_train, y_train = train[ALL_FEATURES], train["dropout_by_day90"].astype(int)
    X_val, y_val = val[ALL_FEATURES], val["dropout_by_day90"].astype(int)
    X_test, y_test = test[ALL_FEATURES], test["dropout_by_day90"].astype(int)

    preprocessor, num_constraints = build_pipeline(CATEGORICAL_FEATURES, NUMERIC_FEATURES)
    preprocessor.fit(X_train)
    cat_feature_count = len(preprocessor.named_transformers_["cat"].get_feature_names_out())
    full_constraints = tuple([0] * cat_feature_count + list(num_constraints))

    scale_pos = (len(y_train) - y_train.sum()) / y_train.sum()
    classifier = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos,
        monotone_constraints=full_constraints,
        eval_metric="aucpr",
        random_state=random_state,
    )

    pipeline = Pipeline([("preprocess", preprocessor), ("model", classifier)])
    pipeline.fit(X_train, y_train)

    val_probs = pipeline.predict_proba(X_val)[:, 1]
    best_thresh = 0.5
    best_f1 = 0.0
    for t in np.linspace(0.05, 0.95, 181):
        f = f1_score(y_val, (val_probs >= t).astype(int), zero_division=0)
        if f > best_f1:
            best_f1 = f
            best_thresh = float(t)

    test_probs = pipeline.predict_proba(X_test)[:, 1]
    test_preds = (test_probs >= best_thresh).astype(int)
    tn, fp, _fn, _tp = confusion_matrix(y_test, test_preds).ravel()

    metrics = {
        "validation_best_threshold": best_thresh,
        "validation_best_f1": float(best_f1),
        "test_auroc": float(roc_auc_score(y_test, test_probs)),
        "test_auprc": float(average_precision_score(y_test, test_probs)),
        "test_brier": float(brier_score_loss(y_test, test_probs)),
        "test_f1": float(f1_score(y_test, test_preds)),
        "test_precision": float(precision_score(y_test, test_preds, zero_division=0)),
        "test_recall": float(recall_score(y_test, test_preds)),
        "test_specificity": float(tn / (tn + fp)),
    }
    print("--- Model Performance ---")
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}")

    print("\n--- Scenario Acceptance Checks ---")
    sample_row = X_test.iloc[0].to_dict()

    def _eval_scenario(scheduled: int, missed: int, streak: int) -> float:
        row = dict(sample_row)
        row["scheduled_dose_count"] = scheduled
        row["missed_dose_count"] = missed
        row["missed_dose_rate"] = missed / scheduled if scheduled else 0.0
        row["longest_missed_dose_streak"] = streak
        return float(pipeline.predict_proba(pd.DataFrame([row]))[0, 1])

    p_0_8 = _eval_scenario(8, 0, 0)
    p_2_8 = _eval_scenario(8, 2, 1)
    p_3_8 = _eval_scenario(8, 3, 2)
    p_4_8 = _eval_scenario(8, 4, 3)
    p_8_8 = _eval_scenario(8, 8, 8)
    p_3_3 = _eval_scenario(3, 3, 3)

    print(f"0/8 missed (streak 0): {p_0_8:.4f}")
    print(f"2/8 missed (streak 1): {p_2_8:.4f}")
    print(f"3/8 missed (streak 2): {p_3_8:.4f}")
    print(f"4/8 missed (streak 3): {p_4_8:.4f}")
    print(f"8/8 missed (streak 8): {p_8_8:.4f}")
    print(f"3/3 missed (streak 3): {p_3_3:.4f}")

    assert p_0_8 <= p_2_8 <= p_3_8 <= p_4_8 <= p_8_8, "Monotonicity check failed on dose adherence!"
    assert p_8_8 > p_3_3, "Absolute count distinction check failed (8/8 must be higher than 3/3)!"
    print("ALL SCENARIO ACCEPTANCE CHECKS PASSED.")

    import joblib

    models_dir = output_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, models_dir / "xgboost_pipeline.joblib")

    feature_schema = {
        "version": "r4-day30-features-v2",
        "features": [{"name": col} for col in ALL_FEATURES],
    }
    (output_dir / "feature_schema.json").write_text(json.dumps(feature_schema, indent=2) + "\n")
    (output_dir / "input_example.json").write_text(json.dumps([sample_row], indent=2) + "\n")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    print(f"\nExport complete to: {output_dir}")
    return metrics


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("artifacts/nemo/r3_experiment_4000"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/r4/xgboost_06_candidate")
    )
    args = parser.parse_args()
    train_and_evaluate(args.data_dir, args.output_dir)
