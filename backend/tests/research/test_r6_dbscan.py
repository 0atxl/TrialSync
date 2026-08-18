from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("sklearn", reason="R6 DBSCAN/PCA require the optional scikit-learn dependency")

from trialsync.research.cohort_profiles.contracts import (
    R6FactRecord,
    R6PatientRecord,
    RepresentationContext,
)
from trialsync.research.cohort_profiles.features import (
    build_patient_fact_representation,
)
from trialsync.research.cohorts.dbscan import (
    DBSCANConfig,
    build_pca_projection,
    run_dbscan_analysis,
)


def _artifact():
    patients = tuple(
        R6PatientRecord(
            member_id=f"participant-{index}",
            date_of_birth=date(1970 + (index % 2), 1, 1),
            sex="female" if index % 2 else "male",
            facts=(
                R6FactRecord(
                    f"condition-{index}",
                    "condition",
                    "hypertension" if index < 4 else "asthma",
                    assertion="present",
                    effective_date=date(2026, 8, 1),
                ),
                R6FactRecord(
                    f"observation-{index}",
                    "observation",
                    "hba1c",
                    value=5.5 if index < 4 else 9.0,
                    effective_date=date(2026, 8, 1),
                ),
            ),
        )
        for index in range(8)
    )
    return build_patient_fact_representation(
        patients,
        RepresentationContext("cohort", "panel", "criteria", date(2026, 8, 16)),
    )


def test_dbscan_reports_grid_noise_stability_and_seeded_display_projection() -> None:
    artifact = _artifact()
    report = run_dbscan_analysis(
        artifact,
        DBSCANConfig(eps_values=(0.2, 2.0), min_samples_values=(2,), stability_repeats=2),
        condition_memberships={
            member_id: frozenset({"hypertension" if index < 4 else "asthma"})
            for index, member_id in enumerate(artifact.member_ids)
        },
    )
    first = build_pca_projection(artifact, random_state=99)
    second = build_pca_projection(artifact, random_state=99)

    assert len(report.candidates) == 2
    assert report.selected in report.candidates
    assert report.selected.cluster_count >= 2
    assert "non-trivial multi-cluster" in report.selection_reason
    assert 0.0 <= report.selected.noise_fraction <= 1.0
    assert report.distance_distribution.nearest_neighbor_median >= 0.0
    assert report.condition_composition
    assert first.display_only is True
    assert (first.coordinates == second.coordinates).all()
