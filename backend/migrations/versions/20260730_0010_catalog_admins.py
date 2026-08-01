"""Add an explicit catalog-administrator capability.

Revision ID: 20260730_0010
Revises: 20260729_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0010"
down_revision: str | None = "20260729_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_catalog_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        sa.text(
            "UPDATE users SET is_catalog_admin = TRUE "
            "WHERE email = 'admin@trialsync.example'"
        )
    )


def downgrade() -> None:
    op.drop_column("users", "is_catalog_admin")
