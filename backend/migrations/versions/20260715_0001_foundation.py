"""Establish the empty Phase 1 schema baseline.

Revision ID: 20260715_0001
Revises:
Create Date: 2026-07-15
"""

from collections.abc import Sequence

revision: str = "20260715_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create no domain tables during the foundation phase."""


def downgrade() -> None:
    """Remove no domain tables during the foundation phase."""

