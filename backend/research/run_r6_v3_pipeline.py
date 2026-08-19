"""Run the complete R6 V3 controlled-group cohort pipeline."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from research.analyze_r6_cohort import (
    build_representations,
    load_materialized_cohort,
    write_analysis_artifacts,
)
from research.build_r6_v3_cohort import materialize_v3, write_artifacts_v3
from research.configs.r6_v3 import DEFAULT_V3_CONFIG, R6V3Config
from research.evaluate_r6_v3 import evaluate_run


def run_pipeline(
    output_root: Path, config: R6V3Config = DEFAULT_V3_CONFIG
) -> dict[str, object]:
    """Build one controlled-group V3 run beneath its content-derived run identifier."""

    cohort, assignments = materialize_v3(config)
    output_root.mkdir(parents=True, exist_ok=True)
    run_directory = output_root / cohort.run_id
    if run_directory.exists():
        raise FileExistsError(f"R6 V3 run already exists and is immutable: {run_directory}")
    with tempfile.TemporaryDirectory(prefix=".r6-v3-staging-", dir=output_root) as temporary:
        staging_directory = Path(temporary) / cohort.run_id
        write_artifacts_v3(cohort, staging_directory, assignments)
        loaded = load_materialized_cohort(
            staging_directory,
            expected_run_id=cohort.run_id,
        )
        representations = build_representations(loaded)
        manifest = write_analysis_artifacts(loaded, representations)
        evaluation = evaluate_run(staging_directory)
        staging_directory.rename(run_directory)
    return {
        "run_id": cohort.run_id,
        "run_directory": str(run_directory),
        "active_run_setting": f"TRIALSYNC_RESEARCH_COHORT_ACTIVE_RUN={cohort.run_id}",
        "manifest": manifest,
        "evaluation": evaluation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the complete R6 V3 controlled-group cohort artifact bundle."
    )
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/r6"))
    parser.add_argument("--patients", type=int, default=DEFAULT_V3_CONFIG.patient_count)
    parser.add_argument("--trials", type=int, default=DEFAULT_V3_CONFIG.trial_count)
    args = parser.parse_args()
    result = run_pipeline(
        args.output_root,
        R6V3Config(patient_count=args.patients, trial_count=args.trials),
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
