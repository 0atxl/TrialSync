"""Add bounded screening explanation conversation storage.

Revision ID: 20260716_0006
Revises: 20260715_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0006"
down_revision: str | None = "20260715_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screening_chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "screening_id",
            sa.Uuid(),
            sa.ForeignKey("screenings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("answer_state", sa.String(32), nullable=True),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=True),
        sa.Column("model_id", sa.String(120), nullable=True),
        sa.Column("prompt_version", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_message_role"),
        sa.CheckConstraint(
            "answer_state IS NULL OR answer_state IN "
            "('supported', 'insufficient_evidence', 'refused')",
            name="ck_chat_message_answer_state",
        ),
        sa.CheckConstraint(
            "(role = 'user' AND answer_state IS NULL) OR "
            "(role = 'assistant' AND answer_state IS NOT NULL)",
            name="ck_chat_message_role_state",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_screening_chat_messages_screening_id", "screening_chat_messages", ["screening_id"]
    )
    op.create_index(
        "ix_screening_chat_messages_screening_created",
        "screening_chat_messages",
        ["screening_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("screening_chat_messages")
