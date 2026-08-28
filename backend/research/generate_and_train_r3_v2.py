# ==============================================================================
# TrialSync R3-v2: Fast Generator & Monotonic XGBoost-06 (Calibrated)
# ==============================================================================
"""Historical/experimental research script for generating synthetic data and training XGBoost-06.

Status: Superseded by the explicit v2 training workflow in `research.train_xgboost_v2`.
Preserved for historical reference and research reproducibility.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier


def get_split(eid: str) -> str:
    h = int(hashlib.sha256(eid.encode("utf-8")).hexdigest(), 16) % 100
    return "train" if h < 70 else "validation" if h < 85 else "test"


def main(output_dir: Path | None = None) -> None:
    output_path = output_dir or Path("/kaggle/working/trialsync_v2_bundle")
    output_path.mkdir(parents=True, exist_ok=True)
    models_dir = output_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    seed = 42
    np.random.seed(seed)
    n_participants = 4000

    print(f"--- 1. Generating {n_participants} Synthetic Participants (R3-v2 Calibrated) ---")

    # 1. Baseline Demographics & Clinical Features
    conditions = np.random.choice(
        ["metabolic", "cardiovascular", "renal", "oncology", "respiratory"], size=n_participants
    )
    regions = np.random.choice(["north", "south", "east", "west", "central"], size=n_participants)
    arms = np.random.choice(["active", "control"], size=n_participants)
    sexes = np.random.choice(
        ["female", "male", "intersex_or_other", "not_recorded"],
        p=[0.48, 0.48, 0.01, 0.03],
        size=n_participants,
    )
    ages = np.random.randint(18, 81, size=n_participants)

    base_sev = np.random.uniform(0.05, 0.95, size=n_participants)
    pt_burden = np.clip(
        base_sev * 0.7 + np.random.uniform(-0.2, 0.3, size=n_participants), 0.0, 1.0
    )
    comorb = np.clip(np.random.poisson(lam=(ages / 25)), 0, 4)
    tx_burden = np.random.choice(
        [0, 1, 2, 3, 4], p=[0.1, 0.25, 0.35, 0.20, 0.10], size=n_participants
    )
    travel = np.random.choice(
        [0, 1, 2, 3, 4], p=[0.15, 0.30, 0.30, 0.18, 0.07], size=n_participants
    )
    support = np.clip(
        4 - travel + np.random.choice([-1, 0, 1], p=[0.2, 0.6, 0.2], size=n_participants), 0, 4
    )
    med_count = np.clip(comorb * 2 + np.random.randint(0, 3, size=n_participants), 0, 8)

    # 2. Dosing Regimens (vary between weekly regimens: 8 doses, and daily regimens: 30 doses)
    scheduled_doses = np.random.choice(
        [8, 12, 16, 30], p=[0.25, 0.20, 0.15, 0.40], size=n_participants
    )
    adherence_propensity = np.random.beta(a=0.7, b=4.0, size=n_participants)
    adherence_propensity = np.clip(
        adherence_propensity + 0.06 * (travel >= 3) + 0.05 * (support <= 1), 0.0, 0.98
    )

    missed_doses = np.zeros(n_participants, dtype=int)
    longest_missed_streak = np.zeros(n_participants, dtype=int)

    for i in range(n_participants):
        n_doses = scheduled_doses[i]
        base_p = adherence_propensity[i]
        cur_streak = 0
        max_streak = 0
        m_count = 0
        prev_miss = False

        for _ in range(n_doses):
            p_miss = min(0.96, base_p * 2.2) if prev_miss else base_p
            is_miss = np.random.rand() < p_miss
            if is_miss:
                m_count += 1
                cur_streak += 1
                max_streak = max(max_streak, cur_streak)
                prev_miss = True
            else:
                cur_streak = 0
                prev_miss = False

        missed_doses[i] = m_count
        longest_missed_streak[i] = max_streak

    missed_dose_rate = missed_doses / scheduled_doses

    # Visits
    scheduled_visits = np.full(n_participants, 4)
    missed_visits = np.random.binomial(n=4, p=np.clip(adherence_propensity * 1.1, 0.0, 0.85))
    delayed_visits = np.clip(np.random.binomial(n=4 - missed_visits, p=0.15), 0, 4)
    missed_visit_rate = missed_visits / scheduled_visits
    longest_visit_streak = np.clip(missed_visits, 0, 4)
    mean_visit_delay = delayed_visits * np.random.uniform(1.0, 3.5, size=n_participants)

    # Severity & AEs
    func_obs_count = np.random.choice([3, 4, 5], p=[0.1, 0.7, 0.2], size=n_participants)
    delta = np.where(arms == "active", -0.06, 0.01) + np.random.normal(0, 0.04, size=n_participants)
    latest_sev = np.clip(base_sev + delta, 0.0, 1.0)
    func_slope = (latest_sev - base_sev) / 30.0

    ae_count = np.random.poisson(
        lam=0.35 + 0.25 * (arms == "active") + 0.2 * (base_sev > 0.6), size=n_participants
    )
    ae_burden = ae_count * np.random.choice([1, 2, 3], p=[0.65, 0.25, 0.10], size=n_participants)
    meas_missing_rate = np.clip(
        adherence_propensity * 0.45 + np.random.uniform(0, 0.04, size=n_participants), 0.0, 1.0
    )

    # ------------------------------------------------------------------------------
    # 3. Calibrated Risk Points (Target ~18.5% prevalence)
    # ------------------------------------------------------------------------------
    adh_points = (
        1 * (missed_dose_rate >= 0.20)
        + 2 * (missed_dose_rate >= 0.50)
        + 3 * (missed_dose_rate >= 0.85)
        + 2 * (longest_missed_streak >= 4)
    )

    burd_points = (
        2 * (base_sev >= 0.70)
        + 1 * (ae_burden >= 2)
        + 1 * (travel >= 3)
        + 1 * (support <= 1)
        + 1 * (tx_burden >= 3)
    )

    total_risk_points = adh_points + burd_points

    # 5-Tier response curve calibrated for 18-20% overall cohort prevalence
    true_dropout_prob = np.where(
        (missed_dose_rate >= 0.85) | (total_risk_points >= 8),
        0.88,  # Critical / Total Abandonment
        np.where(
            total_risk_points >= 6,
            0.65,  # Very High
            np.where(
                total_risk_points >= 4,
                0.38,  # High
                np.where(
                    total_risk_points >= 3,
                    0.18,  # Moderate (baseline)
                    0.05,
                ),
            ),
        ),  # Low
    )

    dropout_by_day90 = (np.random.rand(n_participants) < true_dropout_prob).astype(int)

    df = pd.DataFrame(
        {
            "research_enrollment_id": [f"r3-enrollment-{i:05d}" for i in range(n_participants)],
            "condition_category": conditions,
            "site_region": regions,
            "treatment_arm": arms,
            "sex": sexes,
            "age": ages,
            "baseline_functional_severity": np.round(base_sev, 4),
            "patient_reported_burden": np.round(pt_burden, 4),
            "baseline_comorbidity_burden": comorb,
            "baseline_treatment_burden": tx_burden,
            "travel_access_burden": travel,
            "support_availability": support,
            "medication_count": med_count,
            "latest_functional_severity": np.round(latest_sev, 4),
            "functional_severity_slope": np.round(func_slope, 6),
            "functional_observation_count": func_obs_count,
            "scheduled_dose_count": scheduled_doses,
            "missed_dose_count": missed_doses,
            "missed_dose_rate": np.round(missed_dose_rate, 4),
            "longest_missed_dose_streak": longest_missed_streak,
            "scheduled_visit_count": scheduled_visits,
            "missed_visit_count": missed_visits,
            "missed_visit_rate": np.round(missed_visit_rate, 4),
            "longest_missed_visit_streak": longest_visit_streak,
            "delayed_visit_count": delayed_visits,
            "mean_visit_delay_days": np.round(mean_visit_delay, 2),
            "measurement_missingness_rate": np.round(meas_missing_rate, 4),
            "adverse_event_count": ae_count,
            "adverse_event_burden": ae_burden,
            "dropout_by_day90": dropout_by_day90,
        }
    )

    df["dataset_split"] = df["research_enrollment_id"].map(get_split)

    overall_prev = df["dropout_by_day90"].mean() * 100
    print(f"Cohort dropout prevalence: {overall_prev:.2f}% (Target: 18-20%)")
    df.to_parquet(output_path / "landmark_day30_features.parquet", index=False)

    # ------------------------------------------------------------------------------
    # 4. Train Monotonic XGBoost
    # ------------------------------------------------------------------------------
    print("\n--- 2. Training Monotonic XGBoost-06 ---")

    categorical_features = ["condition_category", "site_region", "treatment_arm", "sex"]
    numeric_features = [
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
    all_features = categorical_features + numeric_features

    train = df[df["dataset_split"] == "train"].copy()
    val = df[df["dataset_split"] == "validation"].copy()
    test = df[df["dataset_split"] == "test"].copy()

    x_train, y_train = train[all_features], train["dropout_by_day90"]
    x_val, y_val = val[all_features], val["dropout_by_day90"]
    x_test, y_test = test[all_features], test["dropout_by_day90"]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(sparse_output=False, handle_unknown="ignore"),
                categorical_features,
            ),
            ("num", StandardScaler(), numeric_features),
        ]
    )
    preprocessor.fit(x_train)
    cat_count = len(preprocessor.named_transformers_["cat"].get_feature_names_out())

    numeric_constraints = [0, 1, 1, 1, 1, 1, -1, 0, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    full_constraints = tuple([0] * cat_count + numeric_constraints)

    scale_pos = (len(y_train) - y_train.sum()) / y_train.sum()
    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        scale_pos_weight=scale_pos,
        monotone_constraints=full_constraints,
        eval_metric="aucpr",
        random_state=seed,
    )

    pipeline = Pipeline([("preprocess", preprocessor), ("model", model)])
    pipeline.fit(x_train, y_train)

    # ------------------------------------------------------------------------------
    # 5. Evaluation & Scenario Verification
    # ------------------------------------------------------------------------------
    val_probs = pipeline.predict_proba(x_val)[:, 1]
    best_thresh, best_f1 = 0.5, 0.0
    for t in np.linspace(0.05, 0.95, 181):
        f = f1_score(y_val, (val_probs >= t).astype(int), zero_division=0)
        if f > best_f1:
            best_f1, best_thresh = f, float(t)

    test_probs = pipeline.predict_proba(x_test)[:, 1]
    test_preds = (test_probs >= best_thresh).astype(int)
    tn, fp, _fn, _tp = confusion_matrix(y_test, test_preds).ravel()

    print("\n================ TEST SET METRICS ================")
    print(f"Validation Optimal Threshold: {best_thresh:.4f} (Val F1: {best_f1:.4f})")
    print(f"Test AUROC:                  {roc_auc_score(y_test, test_probs):.4f}")
    print(f"Test AUPRC:                  {average_precision_score(y_test, test_probs):.4f}")
    print(f"Test Brier Score:            {brier_score_loss(y_test, test_probs):.4f}")
    print(f"Test F1 Score:               {f1_score(y_test, test_preds):.4f}")
    print(f"Test Specificity:            {tn / (tn + fp):.4f}")
    print(f"Test Recall:                 {recall_score(y_test, test_preds):.4f}")

    print("\n============== SCENARIO ACCEPTANCE CHECKS ==============")
    sample_row = x_test.iloc[0].to_dict()

    def eval_scenario(scheduled: int, missed: int, streak: int) -> float:
        row = dict(sample_row)
        row["scheduled_dose_count"] = scheduled
        row["missed_dose_count"] = missed
        row["missed_dose_rate"] = missed / scheduled if scheduled else 0.0
        row["longest_missed_dose_streak"] = streak
        return float(pipeline.predict_proba(pd.DataFrame([row]))[0, 1])

    p_0_8 = eval_scenario(8, 0, 0)
    p_2_8 = eval_scenario(8, 2, 1)
    p_3_8 = eval_scenario(8, 3, 2)
    p_4_8 = eval_scenario(8, 4, 3)
    p_8_8 = eval_scenario(8, 8, 8)
    p_3_3 = eval_scenario(3, 3, 3)

    print(f"Scenario 0/8 missed (streak 0): {p_0_8 * 100:.1f}%")
    print(f"Scenario 2/8 missed (streak 1): {p_2_8 * 100:.1f}%")
    print(f"Scenario 3/8 missed (streak 2): {p_3_8 * 100:.1f}%")
    print(f"Scenario 4/8 missed (streak 3): {p_4_8 * 100:.1f}%")
    print(f"Scenario 8/8 missed (streak 8): {p_8_8 * 100:.1f}%")
    print(f"Scenario 3/3 missed (streak 3): {p_3_3 * 100:.1f}%")

    assert p_0_8 <= p_2_8 <= p_3_8 <= p_4_8 <= p_8_8, "Monotonicity violated!"
    assert p_8_8 > p_3_3, "8/8 must be higher risk than 3/3!"
    print("\n>>> ALL SCENARIO ACCEPTANCE CHECKS PASSED WITH FLYING COLORS! <<<")

    # Export
    joblib.dump(pipeline, models_dir / "xgboost_pipeline.joblib")
    schema = {
        "version": "r4-day30-features-v2",
        "features": [{"name": col} for col in all_features],
    }
    (output_path / "feature_schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    (output_path / "input_example.json").write_text(json.dumps([sample_row], indent=2) + "\n")

    metrics = {
        "validation_best_threshold": best_thresh,
        "validation_best_f1": float(best_f1),
        "test_auroc": float(roc_auc_score(y_test, test_probs)),
        "test_auprc": float(average_precision_score(y_test, test_probs)),
        "test_brier": float(brier_score_loss(y_test, test_probs)),
        "test_f1": float(f1_score(y_test, test_preds)),
    }
    (output_path / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"\nArtifacts saved in: {output_path}")


if __name__ == "__main__":
    main()
