"""Canonicalize patient biological sex and enforce supported values.

Revision ID: 20260729_0007
Revises: 20260716_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0007"
down_revision: str | None = "20260716_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE unsupported_count integer;
            BEGIN
                SELECT count(*)
                INTO unsupported_count
                FROM patients
                WHERE sex IS NOT NULL
                  AND lower(btrim(sex)) NOT IN ('male', 'female');

                IF unsupported_count > 0 THEN
                    RAISE EXCEPTION
                        'patient biological-sex migration blocked: % unsupported value(s)',
                        unsupported_count;
                END IF;
            END
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE patients
            SET sex = lower(btrim(sex))
            WHERE sex IS NOT NULL
              AND sex <> lower(btrim(sex))
            """
        )
    )
    op.create_check_constraint(
        "ck_patients_biological_sex",
        "patients",
        "sex IS NULL OR sex IN ('male', 'female')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_patients_biological_sex", "patients", type_="check")
