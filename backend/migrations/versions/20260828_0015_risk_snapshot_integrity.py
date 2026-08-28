"""Make enrollment corrections append-only and repair prediction snapshot links.

Revision ID: 20260828_0015
Revises: 20260827_0014
"""

from __future__ import annotations

import hashlib
import math
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0015"
down_revision: str | None = "20260827_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_XGBOOST_05_MODEL_ID = "886f64ca-8b57-5dd1-babb-7dfa72480fcf"
_XGBOOST_06_MODEL_ID = "c53eac18-2c71-55f5-a247-5228516fcf3f"
_V1_FEATURE_CONTRACT = "r4-day30-features-v1"
_V2_FEATURE_CONTRACT = "r4-day30-features-v2"
_V2_FEATURE_NAMES = frozenset(
    {
        "condition_category",
        "site_region",
        "treatment_arm",
        "sex",
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
    }
)
_V1_FEATURE_NAMES = _V2_FEATURE_NAMES - {
    "scheduled_dose_count",
    "missed_dose_count",
    "longest_missed_dose_streak",
    "missed_visit_count",
    "longest_missed_visit_streak",
}
_CATEGORIES = {
    "condition_category": {"metabolic", "cardiovascular", "renal", "oncology", "respiratory"},
    "site_region": {"central", "north", "south", "east", "west"},
    "treatment_arm": {"active", "control"},
    "sex": {"female", "intersex_or_other", "male", "not_recorded"},
}
_INTEGER_RANGES = {
    "age": (18, 100),
    "baseline_comorbidity_burden": (0, 20),
    "baseline_treatment_burden": (0, 20),
    "travel_access_burden": (0, 4),
    "support_availability": (0, 4),
    "medication_count": (0, 50),
    "functional_observation_count": (0, 100),
    "scheduled_dose_count": (1, 100),
    "missed_dose_count": (0, 100),
    "longest_missed_dose_streak": (0, 30),
    "delayed_visit_count": (0, 100),
    "missed_visit_count": (0, 50),
    "longest_missed_visit_streak": (0, 15),
    "adverse_event_count": (0, 100),
    "adverse_event_burden": (0, 500),
}
_FLOAT_RANGES = {
    "baseline_functional_severity": (0.0, 1.0),
    "patient_reported_burden": (0.0, 1.0),
    "latest_functional_severity": (0.0, 1.0),
    "functional_severity_slope": (-1.0, 1.0),
    "missed_dose_rate": (0.0, 1.0),
    "missed_visit_rate": (0.0, 1.0),
    "mean_visit_delay_days": (0.0, 30.0),
    "measurement_missingness_rate": (0.0, 1.0),
}


def _is_valid_payload(
    values: object, sources: object, expected_names: frozenset[str]
) -> bool:
    if not isinstance(values, dict) or not isinstance(sources, dict):
        return False
    if set(values) != expected_names or set(sources) != expected_names:
        return False
    if not all(isinstance(source, str) and source.strip() for source in sources.values()):
        return False
    for name, value in values.items():
        if name in _CATEGORIES:
            if not isinstance(value, str) or value not in _CATEGORIES[name]:
                return False
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        numeric = float(value)
        if not math.isfinite(numeric):
            return False
        if name in _INTEGER_RANGES:
            lower, upper = _INTEGER_RANGES[name]
            if numeric != int(numeric) or not lower <= int(numeric) <= upper:
                return False
        else:
            lower, upper = _FLOAT_RANGES[name]
            if not lower <= numeric <= upper:
                return False
    if expected_names == _V2_FEATURE_NAMES:
        return (
            int(values["missed_dose_count"]) <= int(values["scheduled_dose_count"])
            and int(values["longest_missed_dose_streak"])
            <= int(values["missed_dose_count"])
            and int(values["longest_missed_visit_streak"])
            <= int(values["missed_visit_count"])
        )
    return True


def _classify_payload(values: object, sources: object) -> str:
    if not isinstance(values, dict) or not isinstance(sources, dict):
        raise RuntimeError("Feature values and sources must both be JSON objects.")
    value_names = set(values)
    source_names = set(sources)
    if value_names == _V2_FEATURE_NAMES and source_names == _V2_FEATURE_NAMES:
        if _is_valid_payload(values, sources, _V2_FEATURE_NAMES):
            return _V2_FEATURE_CONTRACT
        raise RuntimeError("The 27-feature payload is malformed for the v2 contract.")
    if value_names == _V1_FEATURE_NAMES and source_names == _V1_FEATURE_NAMES:
        if _is_valid_payload(values, sources, _V1_FEATURE_NAMES):
            return _V1_FEATURE_CONTRACT
        raise RuntimeError("The 22-feature payload is malformed for the v1 contract.")
    raise RuntimeError(
        "The feature payload is mixed or unknown; expected the exact 22-field v1 "
        "or 27-field v2 contract."
    )


def _insert_xgboost_06(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            """
            INSERT INTO research_model_versions (
                id, model_name, version, alias, candidate_id,
                training_dataset_version, training_dataset_checksum,
                feature_schema_version, feature_schema_checksum, threshold,
                horizon_day, validation_status, metrics_json, artifact_locator,
                artifact_checksum, band_policy_version, disclaimer_version
            ) VALUES (
                :id, 'dropout-xgboost', '2', 'r5_runtime', 'xgboost-06',
                'r3-dataset-contract-v2', :dataset_checksum,
                'r4-day30-features-v2', :feature_schema_checksum, 0.445,
                90, 'user_selected_runtime_after_review', :metrics_json,
                'dropout-xgboost-06-v1/model.joblib', :artifact_checksum,
                'r5-risk-bands-v1', 'r5-research-risk-v1'
            )
            """
        ).bindparams(sa.bindparam("metrics_json", type_=sa.JSON())),
        {
            "id": _XGBOOST_06_MODEL_ID,
            "dataset_checksum": (
                "a2eb65e5a0396553366808dbc1bcd93f86dfe5f282bac0c522e762c3d961ba3d"
            ),
            "feature_schema_checksum": (
                "b047a68c86a006179856824f8c1e92373759f08abb99c994c55084f3834d63d6"
            ),
            "artifact_checksum": (
                "81cd6cd0836f3d6735ecc4173c88da6bf7c6f1fadda8fc827e2056e92ad9cb15"
            ),
            "metrics_json": {
                "test_auroc": 0.8873525073746312,
                "test_auprc": 0.7443997696773371,
                "test_brier": 0.11818322451748466,
                "test_f1": 0.6865671641791045,
            },
        },
    )


def upgrade() -> None:
    op.create_table(
        "research_enrollment_baseline_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "research_enrollment_id",
            sa.Uuid(),
            sa.ForeignKey("research_enrollments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enrollment_date", sa.Date(), nullable=False),
        sa.Column("baseline_values_json", sa.JSON(), nullable=False),
        sa.Column("baseline_sources_json", sa.JSON(), nullable=False),
        sa.Column("baseline_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("feature_contract_version", sa.String(length=80), nullable=False),
        sa.Column(
            "supersedes_revision_id",
            sa.Uuid(),
            sa.ForeignKey("research_enrollment_baseline_revisions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("correction_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("supersedes_revision_id"),
    )
    op.create_index(
        "ix_research_baseline_revisions_owner",
        "research_enrollment_baseline_revisions",
        ["owner_id"],
    )
    op.create_index(
        "ix_research_baseline_revisions_enrollment",
        "research_enrollment_baseline_revisions",
        ["research_enrollment_id"],
    )
    op.create_index(
        "ix_research_baseline_revisions_creator",
        "research_enrollment_baseline_revisions",
        ["created_by_id"],
    )
    op.create_index(
        "ix_research_baseline_revisions_enrollment_created",
        "research_enrollment_baseline_revisions",
        ["research_enrollment_id", "created_at"],
    )
    op.add_column(
        "research_follow_up_snapshots",
        sa.Column("baseline_revision_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_research_follow_up_snapshots_baseline_revision_id",
        "research_follow_up_snapshots",
        "research_enrollment_baseline_revisions",
        ["baseline_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_research_follow_ups_baseline_revision",
        "research_follow_up_snapshots",
        ["baseline_revision_id"],
    )

    connection = op.get_bind()
    _insert_xgboost_06(connection)

    v2_enrollment_ids: set[uuid.UUID] = set()
    follow_ups = list(
        connection.execute(
            sa.text(
                """
                SELECT id, research_enrollment_id, feature_schema_version,
                       feature_values_json, feature_sources_json, status
                FROM research_follow_up_snapshots
                """
            )
        ).mappings()
    )
    for follow_up in follow_ups:
        try:
            contract = _classify_payload(
                follow_up["feature_values_json"], follow_up["feature_sources_json"]
            )
        except RuntimeError as exc:
            known_contract = follow_up["feature_schema_version"]
            if follow_up["status"] == "incomplete" and known_contract in {
                _V1_FEATURE_CONTRACT,
                _V2_FEATURE_CONTRACT,
            }:
                contract = known_contract
            else:
                raise RuntimeError(
                    f"Follow-up snapshot {follow_up['id']} has invalid feature provenance: {exc}"
                ) from exc
        connection.execute(
            sa.text(
                "UPDATE research_follow_up_snapshots "
                "SET feature_schema_version = :version WHERE id = :id"
            ),
            {
                "id": follow_up["id"],
                "version": contract,
            },
        )
        if contract == _V2_FEATURE_CONTRACT:
            v2_enrollment_ids.add(follow_up["research_enrollment_id"])

    predictions = list(
        connection.execute(
            sa.text(
                """
                SELECT id, research_enrollment_id, feature_snapshot_json
                FROM research_predictions
                """
            )
        ).mappings()
    )
    prediction_contracts: dict[uuid.UUID, str] = {}
    for prediction in predictions:
        payload = prediction["feature_snapshot_json"]
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"Prediction {prediction['id']} has a non-object feature snapshot payload."
            )
        try:
            contract = _classify_payload(payload.get("values"), payload.get("sources"))
        except RuntimeError as exc:
            raise RuntimeError(
                f"Prediction {prediction['id']} has invalid feature provenance: {exc}"
            ) from exc
        prediction_contracts[prediction["id"]] = contract
        connection.execute(
            sa.text(
                "UPDATE research_predictions SET model_version_id = :model_id WHERE id = :id"
            ),
            {
                "id": prediction["id"],
                "model_id": (
                    _XGBOOST_06_MODEL_ID
                    if contract == _V2_FEATURE_CONTRACT
                    else _XGBOOST_05_MODEL_ID
                ),
            },
        )
        if contract == _V2_FEATURE_CONTRACT:
            v2_enrollment_ids.add(prediction["research_enrollment_id"])

    enrollments = list(
        connection.execute(
            sa.text(
                """
                SELECT id, owner_id, enrollment_date, baseline_values_json,
                       baseline_sources_json, baseline_snapshot_hash, created_by_id, created_at
                FROM research_enrollments
                """
            )
        ).mappings()
    )
    for enrollment in enrollments:
        connection.execute(
            sa.text(
                "UPDATE research_enrollments "
                "SET feature_contract_version = :version WHERE id = :id"
            ),
            {
                "id": enrollment["id"],
                "version": (
                    _V2_FEATURE_CONTRACT
                    if enrollment["id"] in v2_enrollment_ids
                    else _V1_FEATURE_CONTRACT
                ),
            },
        )

    for enrollment in enrollments:
        revision_id = uuid.uuid4()
        enrollment_id = enrollment["id"]
        connection.execute(
            sa.text(
                """
                INSERT INTO research_enrollment_baseline_revisions (
                    id, owner_id, research_enrollment_id, enrollment_date,
                    baseline_values_json, baseline_sources_json, baseline_snapshot_hash,
                    feature_contract_version, supersedes_revision_id, correction_reason,
                    created_by_id, created_at
                ) VALUES (
                    :id, :owner_id, :research_enrollment_id, :enrollment_date,
                    :baseline_values_json, :baseline_sources_json, :baseline_snapshot_hash,
                    :feature_contract_version, NULL, NULL, :created_by_id, :created_at
                )
                """
            ).bindparams(
                sa.bindparam("baseline_values_json", type_=sa.JSON()),
                sa.bindparam("baseline_sources_json", type_=sa.JSON()),
            ),
            {
                "id": revision_id,
                "owner_id": enrollment["owner_id"],
                "research_enrollment_id": enrollment_id,
                "enrollment_date": enrollment["enrollment_date"],
                "baseline_values_json": enrollment["baseline_values_json"],
                "baseline_sources_json": enrollment["baseline_sources_json"],
                "baseline_snapshot_hash": enrollment["baseline_snapshot_hash"],
                "feature_contract_version": (
                    _V2_FEATURE_CONTRACT
                    if enrollment_id in v2_enrollment_ids
                    else _V1_FEATURE_CONTRACT
                ),
                "created_by_id": enrollment["created_by_id"],
                "created_at": enrollment["created_at"],
            },
        )
        connection.execute(
            sa.text(
                """
                UPDATE research_follow_up_snapshots
                SET baseline_revision_id = :revision_id
                WHERE research_enrollment_id = :enrollment_id
                """
            ),
            {"revision_id": revision_id, "enrollment_id": enrollment_id},
        )

    mismatches = list(
        connection.execute(
            sa.text(
                """
                SELECT p.id AS prediction_id, p.owner_id, p.research_enrollment_id,
                       p.feature_snapshot_json, p.feature_snapshot_hash,
                       f.cutoff_day, f.input_summary_json, f.missing_features_json,
                       f.status, f.created_at
                FROM research_predictions p
                JOIN research_follow_up_snapshots f ON f.id = p.follow_up_snapshot_id
                WHERE p.feature_snapshot_hash IS DISTINCT FROM f.feature_snapshot_hash
                """
            )
        ).mappings()
    )
    for mismatch in mismatches:
        repaired_snapshot_id = uuid.uuid4()
        snapshot = mismatch["feature_snapshot_json"]
        contract = prediction_contracts[mismatch["prediction_id"]]
        repair_checksum = hashlib.sha256(
            f"prediction-snapshot-repair:{mismatch['prediction_id']}".encode()
        ).hexdigest()
        connection.execute(
            sa.text(
                """
                INSERT INTO research_follow_up_snapshots (
                    id, owner_id, research_enrollment_id, baseline_revision_id, cutoff_day,
                    feature_schema_version, feature_values_json, feature_sources_json,
                    feature_snapshot_hash, input_summary_json, event_set_checksum,
                    missing_features_json, status, created_at
                ) VALUES (
                    :id, :owner_id, :research_enrollment_id, NULL, :cutoff_day,
                    :feature_schema_version, :feature_values_json, :feature_sources_json,
                    :feature_snapshot_hash, :input_summary_json, :event_set_checksum,
                    :missing_features_json, :status, :created_at
                )
                """
            ).bindparams(
                sa.bindparam("feature_values_json", type_=sa.JSON()),
                sa.bindparam("feature_sources_json", type_=sa.JSON()),
                sa.bindparam("input_summary_json", type_=sa.JSON()),
                sa.bindparam("missing_features_json", type_=sa.JSON()),
            ),
            {
                "id": repaired_snapshot_id,
                "owner_id": mismatch["owner_id"],
                "research_enrollment_id": mismatch["research_enrollment_id"],
                "cutoff_day": mismatch["cutoff_day"],
                "feature_schema_version": contract,
                "feature_values_json": snapshot["values"],
                "feature_sources_json": snapshot["sources"],
                "feature_snapshot_hash": mismatch["feature_snapshot_hash"],
                "input_summary_json": mismatch["input_summary_json"],
                "event_set_checksum": repair_checksum,
                "missing_features_json": mismatch["missing_features_json"],
                "status": mismatch["status"],
                "created_at": mismatch["created_at"],
            },
        )
        connection.execute(
            sa.text(
                "UPDATE research_predictions SET follow_up_snapshot_id = :snapshot_id "
                "WHERE id = :prediction_id"
            ),
            {
                "snapshot_id": repaired_snapshot_id,
                "prediction_id": mismatch["prediction_id"],
            },
        )


def downgrade() -> None:
    op.drop_index(
        "ix_research_follow_ups_baseline_revision",
        table_name="research_follow_up_snapshots",
    )
    op.drop_constraint(
        "fk_research_follow_up_snapshots_baseline_revision_id",
        "research_follow_up_snapshots",
        type_="foreignkey",
    )
    op.drop_column("research_follow_up_snapshots", "baseline_revision_id")
    op.drop_table("research_enrollment_baseline_revisions")
