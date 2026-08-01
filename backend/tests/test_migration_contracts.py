from __future__ import annotations

import ast
import runpy
from pathlib import Path

from trialsync.db.models import FactType
from trialsync.patient_data import INITIAL_CATALOG_CONCEPTS, INITIAL_OBSERVATION_UNITS

MIGRATION_DIRECTORY = Path(__file__).parents[1] / "migrations" / "versions"
CATALOG_MIGRATION = MIGRATION_DIRECTORY / "20260729_0009_clinical_concept_catalog.py"


def test_migrations_do_not_import_mutable_application_modules() -> None:
    runtime_imports: list[str] = []
    for path in sorted(MIGRATION_DIRECTORY.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                runtime_imports.extend(
                    f"{path.name}: {alias.name}"
                    for alias in node.names
                    if alias.name == "trialsync" or alias.name.startswith("trialsync.")
                )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (node.module == "trialsync" or node.module.startswith("trialsync."))
            ):
                runtime_imports.append(f"{path.name}: {node.module}")

    assert runtime_imports == []


def test_catalog_migration_owns_the_frozen_pd0_seed() -> None:
    namespace = runpy.run_path(str(CATALOG_MIGRATION))
    seed = namespace["_SEED_CONCEPTS"]

    seeded_concepts = {
        (FactType(str(entry["fact_type"])), str(entry["concept"])) for entry in seed
    }
    seeded_observation_units = {
        str(entry["concept"]): str(entry["fixed_unit"])
        for entry in seed
        if entry["fact_type"] == FactType.observation.value
    }

    assert len(seed) == 25
    assert seeded_concepts == INITIAL_CATALOG_CONCEPTS
    assert seeded_observation_units == INITIAL_OBSERVATION_UNITS
    assert all(entry["active"] is True for entry in seed)
