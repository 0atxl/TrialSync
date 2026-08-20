"""Add integrated R5 enrollment, event, snapshot, and prediction records.

Revision ID: 20260820_0013
Revises: 20260802_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0013"
down_revision: str | None = "20260802_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MODEL_ID = "886f64ca-8b57-5dd1-babb-7dfa72480fcf"


def _event_identity(table_name: str) -> list[sa.Column[object]]:
    return [
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
        sa.Column("event_day", sa.Integer(), nullable=False),
        sa.Column("source_label", sa.String(length=120), nullable=False),
        sa.Column(
            "source_document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recorded_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "supersedes_event_id",
            sa.Uuid(),
            sa.ForeignKey(f"{table_name}.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("correction_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("event_day >= 0", name=f"ck_{table_name[:-1]}_day"),
        sa.UniqueConstraint("supersedes_event_id"),
    ]


def _create_event_indexes(table_name: str) -> None:
    op.create_index(f"ix_{table_name}_owner_id", table_name, ["owner_id"])
    op.create_index(
        f"ix_{table_name}_research_enrollment_id", table_name, ["research_enrollment_id"]
    )


def upgrade() -> None:
    op.create_table(
        "research_model_versions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("alias", sa.String(length=40), nullable=False),
        sa.Column("candidate_id", sa.String(length=80), nullable=False),
        sa.Column("training_dataset_version", sa.String(length=80), nullable=False),
        sa.Column("training_dataset_checksum", sa.String(length=64), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=80), nullable=False),
        sa.Column("feature_schema_checksum", sa.String(length=64), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 16), nullable=False),
        sa.Column("horizon_day", sa.Integer(), nullable=False),
        sa.Column("validation_status", sa.String(length=80), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("artifact_locator", sa.String(length=240), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("band_policy_version", sa.String(length=80), nullable=False),
        sa.Column("disclaimer_version", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("threshold > 0 AND threshold < 1", name="ck_research_model_threshold"),
        sa.CheckConstraint("horizon_day > 0", name="ck_research_model_horizon"),
        sa.UniqueConstraint("model_name", "version"),
        sa.UniqueConstraint("candidate_id"),
    )
    op.create_table(
        "research_enrollments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "patient_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("patient_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "trial_version_id",
            sa.Uuid(),
            sa.ForeignKey("trial_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "screening_id",
            sa.Uuid(),
            sa.ForeignKey("screenings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("research_context_checksum", sa.String(length=64), nullable=False, unique=True),
        sa.Column("enrollment_date", sa.Date(), nullable=False),
        sa.Column("observation_cutoff_day", sa.Integer(), nullable=False),
        sa.Column("prediction_horizon_day", sa.Integer(), nullable=False),
        sa.Column("baseline_values_json", sa.JSON(), nullable=False),
        sa.Column("baseline_sources_json", sa.JSON(), nullable=False),
        sa.Column("baseline_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("feature_contract_version", sa.String(length=80), nullable=False),
        sa.Column("tracking_status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("observation_cutoff_day > 0", name="ck_research_enrollment_cutoff"),
        sa.CheckConstraint(
            "prediction_horizon_day > observation_cutoff_day", name="ck_research_enrollment_horizon"
        ),
        sa.CheckConstraint(
            "tracking_status IN ('active', 'closed')", name="ck_research_enrollment_tracking_status"
        ),
        sa.UniqueConstraint("owner_id", "screening_id"),
        sa.UniqueConstraint("owner_id", "patient_snapshot_id", "trial_version_id"),
    )
    for column in (
        "owner_id",
        "patient_snapshot_id",
        "trial_version_id",
        "screening_id",
        "created_by_id",
    ):
        op.create_index(f"ix_research_enrollments_{column}", "research_enrollments", [column])

    op.create_table(
        "research_dose_events",
        *_event_identity("research_dose_events"),
        sa.Column("medication_concept", sa.String(length=160), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("scheduled_count", sa.Integer(), nullable=False),
        sa.Column("administered_count", sa.Integer(), nullable=False),
        sa.Column("dose_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("dose_unit", sa.String(length=40), nullable=True),
        sa.Column("route", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint("scheduled_count >= 1", name="ck_research_dose_scheduled"),
        sa.CheckConstraint(
            "administered_count >= 0 AND administered_count <= scheduled_count",
            name="ck_research_dose_administered",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'administered', 'partially_administered', 'missed', 'held')",
            name="ck_research_dose_status",
        ),
    )
    _create_event_indexes("research_dose_events")
    op.create_table(
        "research_visit_events",
        *_event_identity("research_visit_events"),
        sa.Column("visit_type", sa.String(length=120), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status IN ('scheduled', 'completed', 'delayed', 'missed')",
            name="ck_research_visit_status",
        ),
        sa.CheckConstraint("delay_days IS NULL OR delay_days >= 0", name="ck_research_visit_delay"),
    )
    _create_event_indexes("research_visit_events")
    op.create_table(
        "research_measurements",
        *_event_identity("research_measurements"),
        sa.Column("concept", sa.String(length=160), nullable=False),
        sa.Column("value_numeric", sa.Numeric(18, 6), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("observed", sa.Boolean(), nullable=False),
        sa.Column("observed_date", sa.Date(), nullable=False),
        sa.Column("method", sa.String(length=120), nullable=True),
        sa.Column("reference_range_json", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "(observed AND value_numeric IS NOT NULL AND unit IS NOT NULL) OR "
            "(NOT observed AND value_numeric IS NULL)",
            name="ck_research_measurement_observed_value",
        ),
    )
    _create_event_indexes("research_measurements")
    op.create_table(
        "research_adverse_events",
        *_event_identity("research_adverse_events"),
        sa.Column("event_concept", sa.String(length=160), nullable=False),
        sa.Column("onset_date", sa.Date(), nullable=False),
        sa.Column("severity_grade", sa.Integer(), nullable=False),
        sa.Column("resolved_date", sa.Date(), nullable=True),
        sa.Column("serious", sa.Boolean(), nullable=False),
        sa.Column("relatedness", sa.String(length=16), nullable=False),
        sa.Column("action_taken", sa.String(length=120), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.CheckConstraint("severity_grade BETWEEN 1 AND 4", name="ck_research_adverse_severity"),
        sa.CheckConstraint(
            "relatedness IN ('unrelated', 'unlikely', 'possible', 'probable', "
            "'definite', 'unknown')",
            name="ck_research_adverse_relatedness",
        ),
        sa.CheckConstraint(
            "outcome IN ('ongoing', 'resolved', 'resolved_with_sequelae', 'unknown')",
            name="ck_research_adverse_outcome",
        ),
    )
    _create_event_indexes("research_adverse_events")
    op.create_table(
        "research_follow_up_snapshots",
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
        sa.Column("cutoff_day", sa.Integer(), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=80), nullable=False),
        sa.Column("feature_values_json", sa.JSON(), nullable=False),
        sa.Column("feature_sources_json", sa.JSON(), nullable=False),
        sa.Column("feature_snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("event_set_checksum", sa.String(length=64), nullable=False),
        sa.Column("missing_features_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("cutoff_day > 0", name="ck_research_follow_up_cutoff"),
        sa.CheckConstraint(
            "status IN ('incomplete', 'ready')", name="ck_research_follow_up_status"
        ),
        sa.UniqueConstraint("research_enrollment_id", "cutoff_day", "event_set_checksum"),
    )
    op.create_index(
        "ix_research_follow_up_snapshots_owner_id", "research_follow_up_snapshots", ["owner_id"]
    )
    op.create_index(
        "ix_research_follow_up_snapshots_research_enrollment_id",
        "research_follow_up_snapshots",
        ["research_enrollment_id"],
    )
    op.create_table(
        "research_predictions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "research_enrollment_id",
            sa.Uuid(),
            sa.ForeignKey("research_enrollments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "follow_up_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("research_follow_up_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("research_model_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("feature_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("feature_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("probability", sa.Numeric(18, 16), nullable=False),
        sa.Column("research_label", sa.String(length=32), nullable=False),
        sa.Column("top_contributions_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "probability >= 0 AND probability <= 1", name="ck_research_prediction_probability"
        ),
        sa.CheckConstraint(
            "research_label IN ('lower', 'near_threshold', 'higher')",
            name="ck_research_prediction_label",
        ),
        sa.UniqueConstraint(
            "owner_id", "research_enrollment_id", "model_version_id", "feature_snapshot_hash"
        ),
    )
    for column in (
        "owner_id",
        "research_enrollment_id",
        "follow_up_snapshot_id",
        "model_version_id",
    ):
        op.create_index(f"ix_research_predictions_{column}", "research_predictions", [column])
    op.create_index(
        "ix_research_predictions_owner_created", "research_predictions", ["owner_id", "created_at"]
    )

    model_versions = sa.table(
        "research_model_versions",
        *[
            sa.column(name)
            for name in (
                "id",
                "model_name",
                "version",
                "alias",
                "candidate_id",
                "training_dataset_version",
                "training_dataset_checksum",
                "feature_schema_version",
                "feature_schema_checksum",
                "threshold",
                "horizon_day",
                "validation_status",
                "artifact_locator",
                "artifact_checksum",
                "band_policy_version",
                "disclaimer_version",
            )
        ],
        sa.column("metrics_json", sa.JSON()),
    )
    op.bulk_insert(
        model_versions,
        [
            {
                "id": _MODEL_ID,
                "model_name": "dropout-xgboost",
                "version": "1",
                "alias": "r5_runtime",
                "candidate_id": "xgboost-05",
                "training_dataset_version": "r3-dataset-contract-v1",
                "training_dataset_checksum": (
                    "746a6f63a02c0948205b53767801a775b16fe35d08aafccc522e3fd975e35982"
                ),
                "feature_schema_version": "r4-day30-features-v1",
                "feature_schema_checksum": (
                    "6d0fe2185247cda50f69fc7954bf958c1c61c5cb4ef160cd34b445170236ca83"
                ),
                "threshold": 0.21347740292549133,
                "horizon_day": 90,
                "validation_status": "user_selected_runtime_after_review",
                "metrics_json": {
                    "test_auroc": 0.6807348560079444,
                    "test_auprc": 0.36168335306293786,
                    "test_brier": 0.13310516191712304,
                    "test_f1": 0.4090909090909091,
                },
                "artifact_locator": "dropout-xgboost-05-v1/model.joblib",
                "artifact_checksum": (
                    "ab2377e9a6a81fa39d77805f0f2fe3bfc09b2c957fcd934b62b7a205051b5de7"
                ),
                "band_policy_version": "r5-risk-bands-v1",
                "disclaimer_version": "r5-research-risk-v1",
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("research_predictions")
    op.drop_table("research_follow_up_snapshots")
    op.drop_table("research_adverse_events")
    op.drop_table("research_measurements")
    op.drop_table("research_visit_events")
    op.drop_table("research_dose_events")
    op.drop_table("research_enrollments")
    op.drop_table("research_model_versions")
