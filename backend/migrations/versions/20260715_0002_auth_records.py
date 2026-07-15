"""Add authentication and structured record tables.

Revision ID: 20260715_0002
Revises: 20260715_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0002"
down_revision: str | None = "20260715_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

fact_type = sa.Enum("condition", "medication", "observation", "demographic", name="fact_type")
fact_assertion = sa.Enum("present", "absent", "unknown", name="fact_assertion")
version_status = sa.Enum("draft", "approved", name="version_status")
criterion_kind = sa.Enum("inclusion", "exclusion", name="criterion_kind")


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("sex", sa.String(32), nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "external_id"),
    )
    op.create_index("ix_patients_owner_id", "patients", ["owner_id"])
    op.create_table(
        "patient_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "patient_id",
            sa.Uuid(),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fact_type", fact_type, nullable=False),
        sa.Column("concept", sa.String(160), nullable=False),
        sa.Column("value_numeric", sa.Numeric(18, 6), nullable=True),
        sa.Column("value_text", sa.String(500), nullable=True),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("assertion", fact_assertion, nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source_label", sa.String(120), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_facts_patient_id", "patient_facts", ["patient_id"])
    op.create_index("ix_patient_facts_patient_type", "patient_facts", ["patient_id", "fact_type"])
    op.create_table(
        "trials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("registry_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("condition", sa.String(160), nullable=False),
        sa.Column("phase", sa.String(40), nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "registry_id"),
    )
    op.create_index("ix_trials_owner_id", "trials", ["owner_id"])
    op.create_table(
        "trial_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "trial_id", sa.Uuid(), sa.ForeignKey("trials.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", version_status, nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trial_id", "version"),
    )
    op.create_index("ix_trial_versions_trial_id", "trial_versions", ["trial_id"])
    op.create_table(
        "criteria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "trial_version_id",
            sa.Uuid(),
            sa.ForeignKey("trial_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", criterion_kind, nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("normalized_rule", sa.JSON(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trial_version_id", "order"),
    )
    op.create_index("ix_criteria_trial_version_id", "criteria", ["trial_version_id"])


def downgrade() -> None:
    op.drop_table("criteria")
    op.drop_table("trial_versions")
    op.drop_table("trials")
    op.drop_table("patient_facts")
    op.drop_table("patients")
    op.drop_table("users")
    criterion_kind.drop(op.get_bind())
    version_status.drop(op.get_bind())
    fact_assertion.drop(op.get_bind())
    fact_type.drop(op.get_bind())
