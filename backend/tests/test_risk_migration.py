from __future__ import annotations

import importlib.util
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import AsyncConnection

from trialsync.db.session import get_engine
from trialsync.research.risk.features import FEATURE_NAMES

pytestmark = pytest.mark.anyio

MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260828_0015_risk_snapshot_integrity.py"
)
FORWARD_MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260828_0016_risk_model_provenance.py"
)
XGBOOST_05_ID = uuid.UUID("886f64ca-8b57-5dd1-babb-7dfa72480fcf")
XGBOOST_06_ID = uuid.UUID("c53eac18-2c71-55f5-a247-5228516fcf3f")
V1_FEATURE_NAMES = tuple(
    name
    for name in FEATURE_NAMES
    if name
    not in {
        "scheduled_dose_count",
        "missed_dose_count",
        "longest_missed_dose_streak",
        "missed_visit_count",
        "longest_missed_visit_streak",
    }
)


def _load_migration(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load migration 0015.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _v2_values() -> dict[str, str | int | float]:
    return {
        "condition_category": "respiratory",
        "site_region": "west",
        "treatment_arm": "active",
        "sex": "female",
        "age": 46,
        "baseline_functional_severity": 0.3,
        "patient_reported_burden": 0.2,
        "baseline_comorbidity_burden": 1,
        "baseline_treatment_burden": 2,
        "travel_access_burden": 1,
        "support_availability": 3,
        "medication_count": 2,
        "latest_functional_severity": 0.4,
        "functional_severity_slope": 0.003,
        "functional_observation_count": 4,
        "scheduled_dose_count": 10,
        "missed_dose_count": 2,
        "missed_dose_rate": 0.2,
        "longest_missed_dose_streak": 1,
        "delayed_visit_count": 1,
        "missed_visit_count": 1,
        "missed_visit_rate": 0.5,
        "longest_missed_visit_streak": 1,
        "mean_visit_delay_days": 1.0,
        "measurement_missingness_rate": 0.1,
        "adverse_event_count": 1,
        "adverse_event_burden": 2,
    }


def _tables() -> tuple[sa.MetaData, dict[str, sa.Table]]:
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    models = sa.Table(
        "research_model_versions",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("model_name", sa.String(80), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("alias", sa.String(40), nullable=False),
        sa.Column("candidate_id", sa.String(80), nullable=False, unique=True),
        sa.Column("training_dataset_version", sa.String(80), nullable=False),
        sa.Column("training_dataset_checksum", sa.String(64), nullable=False),
        sa.Column("feature_schema_version", sa.String(80), nullable=False),
        sa.Column("feature_schema_checksum", sa.String(64), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 16), nullable=False),
        sa.Column("horizon_day", sa.Integer(), nullable=False),
        sa.Column("validation_status", sa.String(80), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("artifact_locator", sa.String(240), nullable=False),
        sa.Column("artifact_checksum", sa.String(64), nullable=False),
        sa.Column("band_policy_version", sa.String(80), nullable=False),
        sa.Column("disclaimer_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("model_name", "version"),
    )
    enrollments = sa.Table(
        "research_enrollments",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_date", sa.Date(), nullable=False),
        sa.Column("baseline_values_json", sa.JSON(), nullable=False),
        sa.Column("baseline_sources_json", sa.JSON(), nullable=False),
        sa.Column("baseline_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("feature_contract_version", sa.String(80), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    follow_ups = sa.Table(
        "research_follow_up_snapshots",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("research_enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("cutoff_day", sa.Integer(), nullable=False),
        sa.Column("feature_schema_version", sa.String(80), nullable=False),
        sa.Column("feature_values_json", sa.JSON(), nullable=False),
        sa.Column("feature_sources_json", sa.JSON(), nullable=False),
        sa.Column("feature_snapshot_hash", sa.String(64)),
        sa.Column("input_summary_json", sa.JSON()),
        sa.Column("event_set_checksum", sa.String(64), nullable=False),
        sa.Column("missing_features_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    predictions = sa.Table(
        "research_predictions",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("research_enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("follow_up_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("feature_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("feature_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("probability", sa.Numeric(18, 16), nullable=False),
        sa.Column("research_label", sa.String(32), nullable=False),
        sa.Column("top_contributions_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    return metadata, {
        "users": users,
        "models": models,
        "enrollments": enrollments,
        "follow_ups": follow_ups,
        "predictions": predictions,
    }


async def _run_upgrade(connection: AsyncConnection, migration: ModuleType) -> None:
    def run(sync_connection: sa.Connection) -> None:
        migration.op = Operations(MigrationContext.configure(sync_connection))
        cast(Callable[[], None], migration.upgrade)()

    await connection.run_sync(run)


async def test_0015_preserves_v1_history_and_repairs_only_v2_provenance() -> None:
    schema = f"test_risk_migration_{uuid.uuid4().hex}"
    metadata, tables = _tables()
    owner_id = uuid.uuid4()
    v1_enrollment_id = uuid.uuid4()
    v2_enrollment_id = uuid.uuid4()
    v1_follow_up_id = uuid.uuid4()
    v2_follow_up_id = uuid.uuid4()
    v1_prediction_id = uuid.uuid4()
    v2_prediction_id = uuid.uuid4()
    v2_values = _v2_values()
    v1_values = {name: v2_values[name] for name in V1_FEATURE_NAMES}
    v1_sources = {name: "historical-v1" for name in V1_FEATURE_NAMES}
    v2_sources = {name: "reviewed-v2" for name in FEATURE_NAMES}

    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.run_sync(metadata.create_all)
            await connection.execute(tables["users"].insert(), {"id": owner_id})
            await connection.execute(
                tables["models"].insert(),
                {
                    "id": XGBOOST_05_ID,
                    "model_name": "dropout-xgboost",
                    "version": "1",
                    "alias": "r5_runtime",
                    "candidate_id": "xgboost-05",
                    "training_dataset_version": "r3-dataset-contract-v1",
                    "training_dataset_checksum": "v1-dataset".ljust(64, "0"),
                    "feature_schema_version": "r4-day30-features-v1",
                    "feature_schema_checksum": "v1-schema".ljust(64, "0"),
                    "threshold": Decimal("0.2134774029254913"),
                    "horizon_day": 90,
                    "validation_status": "user_selected_runtime_after_review",
                    "metrics_json": {"test_auroc": 0.68},
                    "artifact_locator": "dropout-xgboost-05-v1/model.joblib",
                    "artifact_checksum": "v1-artifact".ljust(64, "0"),
                    "band_policy_version": "r5-risk-bands-v1",
                    "disclaimer_version": "r5-research-risk-v1",
                },
            )
            await connection.execute(
                tables["enrollments"].insert(),
                [
                    {
                        "id": enrollment_id,
                        "owner_id": owner_id,
                        "enrollment_date": date(2026, 8, 20),
                        "baseline_values_json": {"age": 46},
                        "baseline_sources_json": {"age": "saved"},
                        "baseline_snapshot_hash": f"baseline-{index}".ljust(64, "0"),
                        "feature_contract_version": "r4-day30-features-v1",
                        "created_by_id": owner_id,
                    }
                    for index, enrollment_id in enumerate(
                        (v1_enrollment_id, v2_enrollment_id), start=1
                    )
                ],
            )
            await connection.execute(
                tables["follow_ups"].insert(),
                [
                    {
                        "id": v1_follow_up_id,
                        "owner_id": owner_id,
                        "research_enrollment_id": v1_enrollment_id,
                        "cutoff_day": 30,
                        "feature_schema_version": "r4-day30-features-v1",
                        "feature_values_json": v1_values,
                        "feature_sources_json": v1_sources,
                        "feature_snapshot_hash": "v1-hash".ljust(64, "0"),
                        "input_summary_json": None,
                        "event_set_checksum": "v1-event".ljust(64, "0"),
                        "missing_features_json": [],
                        "status": "ready",
                    },
                    {
                        "id": v2_follow_up_id,
                        "owner_id": owner_id,
                        "research_enrollment_id": v2_enrollment_id,
                        "cutoff_day": 30,
                        "feature_schema_version": "r4-day30-features-v1",
                        "feature_values_json": {**v2_values, "latest_functional_severity": 0.9},
                        "feature_sources_json": v2_sources,
                        "feature_snapshot_hash": "changed-hash".ljust(64, "0"),
                        "input_summary_json": {"scheduled_doses": 10},
                        "event_set_checksum": "v2-event".ljust(64, "0"),
                        "missing_features_json": [],
                        "status": "ready",
                    },
                ],
            )
            await connection.execute(
                tables["predictions"].insert(),
                [
                    {
                        "id": v1_prediction_id,
                        "owner_id": owner_id,
                        "research_enrollment_id": v1_enrollment_id,
                        "follow_up_snapshot_id": v1_follow_up_id,
                        "model_version_id": XGBOOST_05_ID,
                        "feature_snapshot_json": {"values": v1_values, "sources": v1_sources},
                        "feature_snapshot_hash": "v1-hash".ljust(64, "0"),
                        "probability": Decimal("0.25"),
                        "research_label": "near_threshold",
                        "top_contributions_json": [{"feature": "missed_dose_rate"}],
                    },
                    {
                        "id": v2_prediction_id,
                        "owner_id": owner_id,
                        "research_enrollment_id": v2_enrollment_id,
                        "follow_up_snapshot_id": v2_follow_up_id,
                        "model_version_id": XGBOOST_05_ID,
                        "feature_snapshot_json": {"values": v2_values, "sources": v2_sources},
                        "feature_snapshot_hash": "v2-hash".ljust(64, "0"),
                        "probability": Decimal("0.1576620787382126"),
                        "research_label": "lower",
                        "top_contributions_json": [{"feature": "missed_dose_rate"}],
                    },
                ],
            )

            historical_model_before = (
                await connection.execute(
                    sa.select(tables["models"]).where(tables["models"].c.id == XGBOOST_05_ID)
                )
            ).one()
            prediction_contents_before = {
                row.id: (
                    row.feature_snapshot_json,
                    row.feature_snapshot_hash,
                    row.probability,
                    row.research_label,
                    row.top_contributions_json,
                    row.created_at,
                )
                for row in (await connection.execute(sa.select(tables["predictions"]))).all()
            }

            await _run_upgrade(
                connection,
                _load_migration(MIGRATION_PATH, "risk_snapshot_integrity_0015"),
            )

            models = {
                row.candidate_id: row
                for row in (await connection.execute(sa.select(tables["models"]))).all()
            }
            assert models["xgboost-05"].id == XGBOOST_05_ID
            assert models["xgboost-05"].version == "1"
            assert models["xgboost-05"].feature_schema_version == "r4-day30-features-v1"
            assert models["xgboost-05"].candidate_id == historical_model_before.candidate_id
            assert (
                models["xgboost-05"].training_dataset_checksum
                == historical_model_before.training_dataset_checksum
            )
            assert models["xgboost-05"].threshold == historical_model_before.threshold
            assert models["xgboost-05"].metrics_json == historical_model_before.metrics_json
            assert (
                models["xgboost-05"].artifact_checksum
                == historical_model_before.artifact_checksum
            )
            assert models["xgboost-06"].id == XGBOOST_06_ID
            assert models["xgboost-06"].feature_schema_version == "r4-day30-features-v2"

            predictions = {
                row.id: row
                for row in (await connection.execute(sa.select(tables["predictions"]))).all()
            }
            assert predictions[v1_prediction_id].model_version_id == XGBOOST_05_ID
            assert predictions[v1_prediction_id].follow_up_snapshot_id == v1_follow_up_id
            assert predictions[v1_prediction_id].probability == Decimal("0.2500000000000000")
            assert predictions[v2_prediction_id].model_version_id == XGBOOST_06_ID
            assert predictions[v2_prediction_id].follow_up_snapshot_id != v2_follow_up_id
            assert predictions[v2_prediction_id].feature_snapshot_hash == "v2-hash".ljust(64, "0")
            assert predictions[v2_prediction_id].probability == Decimal("0.1576620787382126")
            for prediction_id, prediction in predictions.items():
                assert (
                    prediction.feature_snapshot_json,
                    prediction.feature_snapshot_hash,
                    prediction.probability,
                    prediction.research_label,
                    prediction.top_contributions_json,
                    prediction.created_at,
                ) == prediction_contents_before[prediction_id]

            repaired = (
                await connection.execute(
                    sa.select(tables["follow_ups"]).where(
                        tables["follow_ups"].c.id
                        == predictions[v2_prediction_id].follow_up_snapshot_id
                    )
                )
            ).one()
            assert repaired.feature_schema_version == "r4-day30-features-v2"
            assert (
                repaired.feature_snapshot_hash
                == predictions[v2_prediction_id].feature_snapshot_hash
            )
            assert repaired.feature_values_json == v2_values

            labels = dict(
                (
                    await connection.execute(
                        sa.select(
                            tables["enrollments"].c.id,
                            tables["enrollments"].c.feature_contract_version,
                        )
                    )
                ).all()
            )
            assert labels[v1_enrollment_id] == "r4-day30-features-v1"
            assert labels[v2_enrollment_id] == "r4-day30-features-v2"

            await connection.execute(
                tables["predictions"].update()
                .where(tables["predictions"].c.id == v2_prediction_id)
                .values(model_version_id=XGBOOST_05_ID)
            )
            await connection.execute(
                tables["models"].delete().where(tables["models"].c.id == XGBOOST_06_ID)
            )
            await connection.execute(
                tables["models"].update()
                .where(tables["models"].c.id == XGBOOST_05_ID)
                .values(
                    version="2",
                    candidate_id="xgboost-06",
                    feature_schema_version="r4-day30-features-v2",
                )
            )
            await connection.execute(
                tables["follow_ups"].update().values(
                    feature_schema_version="r4-day30-features-v2"
                )
            )
            await connection.execute(
                tables["enrollments"].update().values(
                    feature_contract_version="r4-day30-features-v2"
                )
            )

            await _run_upgrade(
                connection,
                _load_migration(FORWARD_MIGRATION_PATH, "risk_model_provenance_0016"),
            )

            repaired_models = {
                row.candidate_id: row
                for row in (await connection.execute(sa.select(tables["models"]))).all()
            }
            assert repaired_models["xgboost-05"].id == XGBOOST_05_ID
            assert repaired_models["xgboost-05"].version == "1"
            assert repaired_models["xgboost-06"].id == XGBOOST_06_ID
            repaired_predictions = {
                row.id: row
                for row in (await connection.execute(sa.select(tables["predictions"]))).all()
            }
            assert repaired_predictions[v1_prediction_id].model_version_id == XGBOOST_05_ID
            assert repaired_predictions[v2_prediction_id].model_version_id == XGBOOST_06_ID
            repaired_labels = dict(
                (
                    await connection.execute(
                        sa.select(
                            tables["enrollments"].c.id,
                            tables["enrollments"].c.feature_contract_version,
                        )
                    )
                ).all()
            )
            assert repaired_labels[v1_enrollment_id] == "r4-day30-features-v1"
            assert repaired_labels[v2_enrollment_id] == "r4-day30-features-v2"
        finally:
            await transaction.rollback()


@pytest.mark.parametrize(
    ("migration_path", "module_name"),
    [
        (MIGRATION_PATH, "risk_snapshot_integrity_0015_invalid"),
        (FORWARD_MIGRATION_PATH, "risk_model_provenance_0016_invalid"),
    ],
)
@pytest.mark.parametrize("invalid_payload_kind", ["mixed", "malformed_v2"])
async def test_risk_migration_rejects_unknown_prediction_without_partial_changes(
    migration_path: Path, module_name: str, invalid_payload_kind: str
) -> None:
    schema = f"test_risk_migration_invalid_{uuid.uuid4().hex}"
    metadata, tables = _tables()
    owner_id = uuid.uuid4()
    enrollment_id = uuid.uuid4()
    follow_up_id = uuid.uuid4()
    prediction_id = uuid.uuid4()
    v2_values = _v2_values()
    v1_values = {name: v2_values[name] for name in V1_FEATURE_NAMES}
    v1_sources = {name: "historical-v1" for name in V1_FEATURE_NAMES}
    if invalid_payload_kind == "mixed":
        invalid_values = {**v1_values, "scheduled_dose_count": 10}
        invalid_sources = {
            **v1_sources,
            "scheduled_dose_count": "unexpected-mixed-field",
        }
    else:
        invalid_values = {
            **v2_values,
            "scheduled_dose_count": 1,
            "missed_dose_count": 2,
        }
        invalid_sources = {name: "malformed-v2" for name in FEATURE_NAMES}

    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.run_sync(metadata.create_all)
            await connection.execute(tables["users"].insert(), {"id": owner_id})
            await connection.execute(
                tables["models"].insert(),
                {
                    "id": XGBOOST_05_ID,
                    "model_name": "dropout-xgboost",
                    "version": "1",
                    "alias": "r5_runtime",
                    "candidate_id": "xgboost-05",
                    "training_dataset_version": "r3-dataset-contract-v1",
                    "training_dataset_checksum": "v1-dataset".ljust(64, "0"),
                    "feature_schema_version": "r4-day30-features-v1",
                    "feature_schema_checksum": "v1-schema".ljust(64, "0"),
                    "threshold": Decimal("0.2134774029254913"),
                    "horizon_day": 90,
                    "validation_status": "user_selected_runtime_after_review",
                    "metrics_json": {"test_auroc": 0.68},
                    "artifact_locator": "dropout-xgboost-05-v1/model.joblib",
                    "artifact_checksum": "v1-artifact".ljust(64, "0"),
                    "band_policy_version": "r5-risk-bands-v1",
                    "disclaimer_version": "r5-research-risk-v1",
                },
            )
            await connection.execute(
                tables["enrollments"].insert(),
                {
                    "id": enrollment_id,
                    "owner_id": owner_id,
                    "enrollment_date": date(2026, 8, 20),
                    "baseline_values_json": {"age": 46},
                    "baseline_sources_json": {"age": "saved"},
                    "baseline_snapshot_hash": "baseline".ljust(64, "0"),
                    "feature_contract_version": "r4-day30-features-v1",
                    "created_by_id": owner_id,
                },
            )
            await connection.execute(
                tables["follow_ups"].insert(),
                {
                    "id": follow_up_id,
                    "owner_id": owner_id,
                    "research_enrollment_id": enrollment_id,
                    "cutoff_day": 30,
                    "feature_schema_version": "r4-day30-features-v1",
                    "feature_values_json": v1_values,
                    "feature_sources_json": v1_sources,
                    "feature_snapshot_hash": "v1-hash".ljust(64, "0"),
                    "input_summary_json": None,
                    "event_set_checksum": "v1-event".ljust(64, "0"),
                    "missing_features_json": [],
                    "status": "ready",
                },
            )
            await connection.execute(
                tables["predictions"].insert(),
                {
                    "id": prediction_id,
                    "owner_id": owner_id,
                    "research_enrollment_id": enrollment_id,
                    "follow_up_snapshot_id": follow_up_id,
                    "model_version_id": XGBOOST_05_ID,
                    "feature_snapshot_json": {
                        "values": invalid_values,
                        "sources": invalid_sources,
                    },
                    "feature_snapshot_hash": "mixed-hash".ljust(64, "0"),
                    "probability": Decimal("0.25"),
                    "research_label": "near_threshold",
                    "top_contributions_json": [{"feature": "missed_dose_rate"}],
                },
            )

            savepoint = await connection.begin_nested()
            with pytest.raises(RuntimeError, match=r"malformed|mixed or unknown"):
                await _run_upgrade(
                    connection,
                    _load_migration(migration_path, module_name),
                )
            await savepoint.rollback()

            models = (
                await connection.execute(
                    sa.select(
                        tables["models"].c.id,
                        tables["models"].c.candidate_id,
                        tables["models"].c.feature_schema_version,
                    )
                )
            ).all()
            assert models == [
                (XGBOOST_05_ID, "xgboost-05", "r4-day30-features-v1")
            ]
            assert (
                await connection.execute(
                    sa.select(tables["follow_ups"].c.feature_schema_version).where(
                        tables["follow_ups"].c.id == follow_up_id
                    )
                )
            ).scalar_one() == "r4-day30-features-v1"

            def migration_ddl_was_rolled_back(sync_connection: sa.Connection) -> bool:
                inspector = sa.inspect(sync_connection)
                follow_up_columns = {
                    column["name"]
                    for column in inspector.get_columns("research_follow_up_snapshots")
                }
                return (
                    not inspector.has_table("research_enrollment_baseline_revisions")
                    and "baseline_revision_id" not in follow_up_columns
                )

            if migration_path == MIGRATION_PATH:
                assert await connection.run_sync(migration_ddl_was_rolled_back)
        finally:
            await transaction.rollback()
