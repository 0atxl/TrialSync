"""Store compact day-30 prediction inputs.

Revision ID: 20260827_0014
Revises: 20260820_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0014"
down_revision: str | None = "20260820_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_follow_up_snapshots",
        sa.Column("input_summary_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_follow_up_snapshots", "input_summary_json")
