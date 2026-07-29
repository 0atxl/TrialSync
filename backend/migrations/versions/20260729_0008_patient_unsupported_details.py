"""Add non-screening patient unsupported-detail review items.

Revision ID: 20260729_0008
Revises: 20260729_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0008"
down_revision: str | None = "20260729_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patient_unsupported_details",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("context", sa.String(length=500), nullable=True),
        sa.Column(
            "source_label",
            sa.String(length=120),
            nullable=False,
            server_default="Manual review item",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "category IN ('condition', 'medication', 'observation', 'other')",
            name="ck_patient_unsupported_detail_category",
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_patient_unsupported_details_patient_id",
        "patient_unsupported_details",
        ["patient_id"],
    )
    op.create_index(
        "ix_patient_unsupported_details_patient_category",
        "patient_unsupported_details",
        ["patient_id", "category"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_patient_unsupported_details_patient_category",
        table_name="patient_unsupported_details",
    )
    op.drop_index(
        "ix_patient_unsupported_details_patient_id",
        table_name="patient_unsupported_details",
    )
    op.drop_table("patient_unsupported_details")
