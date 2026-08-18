"""Run the complete credential-free R6 materialization and analysis pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.analyze_r6_cohort import (
    build_representations,
    load_materialized_cohort,
    write_analysis_artifacts,
)
from research.build_r6_cohort import materialize, write_artifacts
from research.configs.r6_cohort import DEFAULT_CONFIG, R6CohortConfig


def run_pipeline(output_root: Path, config: R6CohortConfig = DEFAULT_CONFIG) -> dict[str, object]:
    """Build one deterministic run beneath its content-derived run identifier."""

    cohort = materialize(config)
    run_directory = output_root / cohort.run_id
    write_artifacts(cohort, run_directory)
    loaded = load_materialized_cohort(run_directory)
    representations = build_representations(loaded)
    manifest = write_analysis_artifacts(loaded, representations)
    return {
        "run_id": cohort.run_id,
        "run_directory": str(run_directory),
        "active_run_setting": f"TRIALSYNC_RESEARCH_COHORT_ACTIVE_RUN={cohort.run_id}",
        "manifest": manifest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the complete R6 cohort artifact bundle.")
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/r6"))
    parser.add_argument("--patients", type=int, default=DEFAULT_CONFIG.patient_count)
    parser.add_argument("--trials", type=int, default=DEFAULT_CONFIG.trial_count)
    args = parser.parse_args()
    result = run_pipeline(
        args.output_root,
        R6CohortConfig(patient_count=args.patients, trial_count=args.trials),
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
