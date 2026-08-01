"""Add reversible fact voiding and immutable patient activity.

Revision ID: 20260802_0012
Revises: 20260730_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0012"
down_revision: str | None = "20260730_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "patient_facts",
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "patient_facts",
        sa.Column("void_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "patient_facts",
        sa.Column(
            "voided_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_table(
        "patient_change_events",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "patient_id",
            sa.Uuid(),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_patient_change_events_patient_id", "patient_change_events", ["patient_id"]
    )
    op.create_index(
        "ix_patient_change_events_actor_id", "patient_change_events", ["actor_id"]
    )
    op.create_index(
        "ix_patient_change_events_patient_created",
        "patient_change_events",
        ["patient_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_patient_change_events_patient_created", table_name="patient_change_events")
    op.drop_index("ix_patient_change_events_actor_id", table_name="patient_change_events")
    op.drop_index("ix_patient_change_events_patient_id", table_name="patient_change_events")
    op.drop_table("patient_change_events")
    op.drop_column("patient_facts", "voided_by_id")
    op.drop_column("patient_facts", "void_reason")
    op.drop_column("patient_facts", "voided_at")
