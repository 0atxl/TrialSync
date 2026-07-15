"""Store immutable presentation labels for saved screening evidence.

Revision ID: 20260715_0004
Revises: 20260715_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0004"
down_revision: str | None = "20260715_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "criterion_evaluations", sa.Column("criterion_source_text", sa.Text(), nullable=True)
    )
    op.execute(
        "UPDATE criterion_evaluations AS evaluation "
        "SET criterion_source_text = criterion.source_text "
        "FROM criteria AS criterion WHERE evaluation.criterion_id = criterion.id"
    )
    op.alter_column("criterion_evaluations", "criterion_source_text", nullable=False)

    op.add_column("screenings", sa.Column("trial_registry_id", sa.String(64), nullable=True))
    op.add_column("screenings", sa.Column("trial_title", sa.String(240), nullable=True))
    op.add_column("screenings", sa.Column("trial_version_number", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE screenings AS screening SET trial_registry_id = trial.registry_id, "
        "trial_title = trial.title, trial_version_number = version.version "
        "FROM trial_versions AS version JOIN trials AS trial ON trial.id = version.trial_id "
        "WHERE screening.trial_version_id = version.id"
    )
    for column in ("trial_registry_id", "trial_title", "trial_version_number"):
        op.alter_column("screenings", column, nullable=False)

    op.execute(
        "UPDATE criterion_evaluations SET canonical_explanation = "
        "'“' || criterion_source_text || '” ' || CASE result::text "
        "WHEN 'pass' THEN 'passed using the recorded evidence.' "
        "WHEN 'fail' THEN 'failed using the recorded evidence.' "
        "ELSE 'is unknown. Additional recorded information is required.' END"
    )


def downgrade() -> None:
    op.drop_column("screenings", "trial_version_number")
    op.drop_column("screenings", "trial_title")
    op.drop_column("screenings", "trial_registry_id")
    op.drop_column("criterion_evaluations", "criterion_source_text")
