"""Store optional terminology provenance for local clinical concepts.

Revision ID: 20260730_0011
Revises: 20260730_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0011"
down_revision: str | None = "20260730_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clinical_concepts", sa.Column("terminology_system", sa.String(32)))
    op.add_column("clinical_concepts", sa.Column("terminology_code", sa.String(80)))


def downgrade() -> None:
    op.drop_column("clinical_concepts", "terminology_code")
    op.drop_column("clinical_concepts", "terminology_system")
