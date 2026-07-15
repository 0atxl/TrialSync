"""Add immutable screening inputs and evidence-backed screening history.

Revision ID: 20260715_0003
Revises: 20260715_0002
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0003"
down_revision: str | None = "20260715_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

overall_state = postgresql.ENUM(
    "potentially_eligible", "likely_ineligible", "needs_review", name="overall_state"
)
evaluation_result = postgresql.ENUM("pass", "fail", "unknown", name="evaluation_result")
overall_state_column = postgresql.ENUM(
    "potentially_eligible",
    "likely_ineligible",
    "needs_review",
    name="overall_state",
    create_type=False,
)
evaluation_result_column = postgresql.ENUM(
    "pass", "fail", "unknown", name="evaluation_result", create_type=False
)
criterion_kind_column = postgresql.ENUM(
    "inclusion", "exclusion", name="criterion_kind", create_type=False
)


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    overall_state.create(op.get_bind(), checkfirst=True)
    evaluation_result.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "patient_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("snapshot_version", sa.String(64), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("facts_json", sa.JSON(), nullable=False),
        sa.Column("source_summary", sa.JSON(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id", "content_hash"),
    )
    op.create_index("ix_patient_snapshots_owner_id", "patient_snapshots", ["owner_id"])
    op.create_index("ix_patient_snapshots_patient_id", "patient_snapshots", ["patient_id"])
    op.create_table(
        "screening_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column("pair_count", sa.Integer(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_screening_batches_owner_id", "screening_batches", ["owner_id"])
    op.create_table(
        "screenings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("screening_batches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("patient_snapshot_id", sa.Uuid(), sa.ForeignKey("patient_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trial_version_id", sa.Uuid(), sa.ForeignKey("trial_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("overall_state", overall_state_column, nullable=False),
        sa.Column("screening_date", sa.Date(), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("dsl_version", sa.String(20), nullable=False),
        sa.Column("terminology_version", sa.String(40), nullable=False),
        sa.Column("unit_version", sa.String(40), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_screenings_owner_id", "screenings", ["owner_id"])
    op.create_index("ix_screenings_batch_id", "screenings", ["batch_id"])
    op.create_index("ix_screenings_patient_snapshot_id", "screenings", ["patient_snapshot_id"])
    op.create_index("ix_screenings_trial_version_id", "screenings", ["trial_version_id"])
    op.create_table(
        "criterion_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("screening_id", sa.Uuid(), sa.ForeignKey("screenings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), sa.ForeignKey("criteria.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("criterion_order", sa.Integer(), nullable=False),
        sa.Column("criterion_kind", criterion_kind_column, nullable=False),
        sa.Column("result", evaluation_result_column, nullable=False),
        sa.Column("truth", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("canonical_explanation", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("rejected_evidence_json", sa.JSON(), nullable=False),
        sa.Column("missing_information_json", sa.JSON(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("screening_id", "criterion_id"),
    )
    op.create_index("ix_criterion_evaluations_screening_id", "criterion_evaluations", ["screening_id"])
    op.create_index("ix_criterion_evaluations_criterion_id", "criterion_evaluations", ["criterion_id"])


def downgrade() -> None:
    op.drop_table("criterion_evaluations")
    op.drop_table("screenings")
    op.drop_table("screening_batches")
    op.drop_table("patient_snapshots")
    evaluation_result.drop(op.get_bind(), checkfirst=True)
    overall_state.drop(op.get_bind(), checkfirst=True)
