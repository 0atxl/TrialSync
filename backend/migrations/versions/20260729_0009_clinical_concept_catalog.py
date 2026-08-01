"""Move the runtime clinical-entry catalog into PostgreSQL.

Revision ID: 20260729_0009
Revises: 20260729_0008
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0009"
down_revision: str | None = "20260729_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALL_ASSERTIONS = ["present", "absent", "unknown"]
_OBSERVATION_ASSERTIONS = ["present", "unknown"]


def _status(
    key: str,
    label: str,
    fact_type: str,
    group: str,
    order: int,
    help_text: str,
) -> dict[str, object]:
    return {
        "key": key,
        "fact_type": fact_type,
        "concept": key,
        "display_label": label,
        "concept_group": group,
        "input_kind": "status",
        "allowed_assertions_json": _ALL_ASSERTIONS,
        "fixed_unit": None,
        "effective_date_required": False,
        "screening_supported": True,
        "help_text": help_text,
        "display_order": order,
        "active": True,
    }


def _observation(
    key: str,
    label: str,
    unit: str,
    order: int,
    help_text: str,
) -> dict[str, object]:
    return {
        "key": key,
        "fact_type": "observation",
        "concept": key,
        "display_label": label,
        "concept_group": "observations",
        "input_kind": "numeric",
        "allowed_assertions_json": _OBSERVATION_ASSERTIONS,
        "fixed_unit": unit,
        "effective_date_required": True,
        "screening_supported": True,
        "help_text": help_text,
        "display_order": order,
        "active": True,
    }


# Frozen migration-owned seed. Keep this revision independent from mutable
# application modules so a fresh database always receives the same catalog.
_SEED_CONCEPTS: tuple[dict[str, object], ...] = (
    _status(
        "type1_diabetes",
        "Type 1 diabetes",
        "condition",
        "conditions",
        10,
        "Record whether Type 1 diabetes is present, absent, or unknown.",
    ),
    _status(
        "type2_diabetes",
        "Type 2 diabetes",
        "condition",
        "conditions",
        20,
        "Record whether Type 2 diabetes is present, absent, or unknown.",
    ),
    _status(
        "hypertension",
        "Hypertension",
        "condition",
        "conditions",
        30,
        "Record whether hypertension is present, absent, or unknown.",
    ),
    _status(
        "asthma",
        "Asthma",
        "condition",
        "conditions",
        40,
        "Record whether asthma is present, absent, or unknown.",
    ),
    {
        "key": "pregnancy",
        "fact_type": "condition",
        "concept": "pregnancy",
        "display_label": "Pregnancy status",
        "concept_group": "conditions",
        "input_kind": "pregnancy_status",
        "allowed_assertions_json": _ALL_ASSERTIONS,
        "fixed_unit": None,
        "effective_date_required": True,
        "screening_supported": True,
        "help_text": "Record the assessed pregnancy status and assessment date.",
        "display_order": 50,
        "active": True,
    },
    _status(
        "metformin",
        "Metformin",
        "medication",
        "medications",
        10,
        "Record whether metformin use is present, absent, or unknown.",
    ),
    _status(
        "atorvastatin",
        "Atorvastatin",
        "medication",
        "medications",
        20,
        "Record whether atorvastatin use is present, absent, or unknown.",
    ),
    _status(
        "insulin",
        "Insulin",
        "medication",
        "medications",
        30,
        "Record whether insulin use is present, absent, or unknown.",
    ),
    _status(
        "semaglutide",
        "Semaglutide",
        "medication",
        "medications",
        40,
        "Record whether semaglutide use is present, absent, or unknown.",
    ),
    _observation("hba1c", "HbA1c", "%", 10, "Record the measured HbA1c result."),
    _observation(
        "fasting_glucose",
        "Fasting glucose",
        "mg/dL",
        20,
        "Record the measured fasting glucose result.",
    ),
    _observation(
        "egfr",
        "eGFR",
        "mL/min/1.73m2",
        30,
        "Record the measured estimated filtration rate.",
    ),
    _observation(
        "creatinine", "Creatinine", "mg/dL", 40, "Record the measured creatinine result."
    ),
    _observation("alt", "ALT", "U/L", 50, "Record the measured alanine transaminase result."),
    _observation("ast", "AST", "U/L", 60, "Record the measured aspartate transaminase result."),
    _observation("hemoglobin", "Hemoglobin", "g/dL", 70, "Record the measured hemoglobin result."),
    _observation(
        "wbc",
        "White blood cell count",
        "10^9/L",
        80,
        "Record the measured white blood cell count.",
    ),
    _observation("platelets", "Platelets", "10^9/L", 90, "Record the measured platelet count."),
    _observation("ldl", "LDL cholesterol", "mg/dL", 100, "Record the measured LDL result."),
    _observation(
        "triglycerides",
        "Triglycerides",
        "mg/dL",
        110,
        "Record the measured triglyceride result.",
    ),
    _observation("bmi", "BMI", "kg/m2", 120, "Record the measured body mass index."),
    _observation(
        "systolic_bp",
        "Systolic blood pressure",
        "mmHg",
        130,
        "Record the measured systolic blood pressure.",
    ),
    _observation(
        "diastolic_bp",
        "Diastolic blood pressure",
        "mmHg",
        140,
        "Record the measured diastolic blood pressure.",
    ),
    _observation("potassium", "Potassium", "mmol/L", 150, "Record the measured potassium result."),
    _observation("albumin", "Albumin", "g/dL", 160, "Record the measured albumin result."),
)


def upgrade() -> None:
    op.create_table(
        "clinical_concepts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column(
            "fact_type",
            postgresql.ENUM(
                "condition",
                "medication",
                "observation",
                "demographic",
                name="fact_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("concept", sa.String(length=160), nullable=False),
        sa.Column("display_label", sa.String(length=120), nullable=False),
        sa.Column("concept_group", sa.String(length=24), nullable=False),
        sa.Column("input_kind", sa.String(length=24), nullable=False),
        sa.Column("allowed_assertions_json", sa.JSON(), nullable=False),
        sa.Column("fixed_unit", sa.String(length=40), nullable=True),
        sa.Column("effective_date_required", sa.Boolean(), nullable=False),
        sa.Column("screening_supported", sa.Boolean(), nullable=False),
        sa.Column("help_text", sa.String(length=300), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
            "concept_group IN ('conditions', 'medications', 'observations')",
            name="ck_clinical_concepts_group",
        ),
        sa.CheckConstraint(
            "input_kind IN ('status', 'pregnancy_status', 'numeric')",
            name="ck_clinical_concepts_input_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
        sa.UniqueConstraint("fact_type", "concept"),
    )
    op.create_index("ix_clinical_concepts_active", "clinical_concepts", ["active"])
    op.create_index("ix_clinical_concepts_key", "clinical_concepts", ["key"])
    concept_table = sa.table(
        "clinical_concepts",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("key", sa.String()),
        sa.column(
            "fact_type",
            postgresql.ENUM(
                "condition",
                "medication",
                "observation",
                "demographic",
                name="fact_type",
                create_type=False,
            ),
        ),
        sa.column("concept", sa.String()),
        sa.column("display_label", sa.String()),
        sa.column("concept_group", sa.String()),
        sa.column("input_kind", sa.String()),
        sa.column("allowed_assertions_json", sa.JSON()),
        sa.column("fixed_unit", sa.String()),
        sa.column("effective_date_required", sa.Boolean()),
        sa.column("screening_supported", sa.Boolean()),
        sa.column("help_text", sa.String()),
        sa.column("display_order", sa.Integer()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        concept_table,
        [
            {
                "id": uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"https://trialsync.local/clinical-concept/{entry['key']}",
                ),
                **entry,
            }
            for entry in _SEED_CONCEPTS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_clinical_concepts_key", table_name="clinical_concepts")
    op.drop_index("ix_clinical_concepts_active", table_name="clinical_concepts")
    op.drop_table("clinical_concepts")
