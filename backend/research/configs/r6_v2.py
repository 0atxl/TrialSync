"""Frozen source and acceptance contract for the one-shot R6 V2 experiment."""

from __future__ import annotations

R6_V2_EXPERIMENT_VERSION = "r6-representation-experiment-v2"
R6_V2_SOURCE_RUN_ID = "r6-c21e487e-3b0d-5562-b7ad-3c7e7bbfdf2f"
R6_V2_EXPECTED_COUNTS = {
    "patient_count": 750,
    "trial_count": 20,
    "pair_count": 15_000,
    "criterion_result_count": 60_000,
}
R6_V2_EXPECTED_SEMANTIC_CHECKSUMS = {
    "cohort": "77d3ef0f289aec1402c84e1f771fe80f3a8c4e843c3981069905da56c78f68a2",
    "reference_panel": "a9e0f6b06ce8c440f18f46d34217f0d642ecd4ea9b65a415111454963f1c686b",
    "criterion_order": "60825a8e975106d7a01558027a1407c57ebcc579db8b7c0c8f16f4bb00cab641",
}

R6_V2_ACCEPTANCE = {
    "minimum_cluster_count": 2,
    "minimum_noise_fraction": 0.05,
    "maximum_noise_fraction": 0.50,
    "minimum_silhouette": 0.05,
    "minimum_bootstrap_ari": 0.50,
    "minimum_nearby_parameter_ari": 0.50,
    "maximum_largest_cluster_fraction": 0.75,
}
