"""NeMo Data Designer configurations for the linked R3 source tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import data_designer.config as dd

TABLES = (
    "participants",
    "enrollments",
    "dose_events",
    "visit_events",
    "measurements",
    "adverse_events",
    "outcomes",
)


def _arguments(params: dd.DataDesignerScriptParams | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--table", choices=TABLES, default="participants")
    parser.add_argument("--seed-path", type=Path)
    return parser.parse_args(list(params.argv if params else ()))


def _builder(seed_path: Path | None) -> dd.DataDesignerConfigBuilder:
    # R3 uses sampler and expression columns only. Omitting unused model configs
    # avoids provider readiness checks without changing Data Designer generation.
    builder = dd.DataDesignerConfigBuilder(model_configs=[])
    if seed_path is not None:
        builder.with_seed_dataset(dd.LocalFileSeedSource(path=str(seed_path)))
    return builder


def _uuid(builder: dd.DataDesignerConfigBuilder, name: str, prefix: str) -> None:
    builder.add_column(
        dd.SamplerColumnConfig(
            name=name,
            sampler_type=dd.SamplerType.UUID,
            params=dd.UUIDSamplerParams(prefix=prefix),
        )
    )


def _category(
    builder: dd.DataDesignerConfigBuilder,
    name: str,
    values: list[str | int],
    weights: list[float] | None = None,
) -> None:
    builder.add_column(
        dd.SamplerColumnConfig(
            name=name,
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=values, weights=weights),
        )
    )


def _conditional_category(
    builder: dd.DataDesignerConfigBuilder,
    name: str,
    *,
    values: list[str | int],
    weights: list[float] | None,
    conditional: dict[str, tuple[list[str | int], list[float] | None]],
) -> None:
    builder.add_column(
        dd.SamplerColumnConfig(
            name=name,
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=values, weights=weights),
            conditional_params={
                condition: dd.CategorySamplerParams(
                    values=conditional_values,
                    weights=conditional_weights,
                )
                for condition, (conditional_values, conditional_weights) in conditional.items()
            },
        )
    )


def _uniform(
    builder: dd.DataDesignerConfigBuilder,
    name: str,
    low: float,
    high: float,
    *,
    convert_to: str | None = None,
) -> None:
    builder.add_column(
        dd.SamplerColumnConfig(
            name=name,
            sampler_type=dd.SamplerType.UNIFORM,
            params=dd.UniformSamplerParams(low=low, high=high),
            convert_to=convert_to,
        )
    )


def _gaussian(
    builder: dd.DataDesignerConfigBuilder,
    name: str,
    mean: float,
    stddev: float,
) -> None:
    builder.add_column(
        dd.SamplerColumnConfig(
            name=name,
            sampler_type=dd.SamplerType.GAUSSIAN,
            params=dd.GaussianSamplerParams(mean=mean, stddev=stddev),
        )
    )


def _expression(
    builder: dd.DataDesignerConfigBuilder,
    name: str,
    expr: str,
    dtype: str,
) -> None:
    builder.add_column(
        dd.ExpressionColumnConfig(
            name=name,
            expr=expr,
            dtype=dtype,
        )
    )


def _participants() -> dd.DataDesignerConfigBuilder:
    builder = _builder(None)
    _uuid(builder, "research_participant_id", "r3-participant-")
    _category(
        builder,
        "condition_category",
        ["metabolic", "cardiovascular", "renal", "oncology", "respiratory"],
        [0.2] * 5,
    )
    _uniform(builder, "age", 18, 80, convert_to="int")
    _category(
        builder,
        "sex",
        ["female", "male", "intersex_or_other", "not_recorded"],
        [0.48, 0.48, 0.01, 0.03],
    )
    _category(
        builder,
        "site_region",
        ["north", "south", "east", "west", "central"],
        [0.2] * 5,
    )
    _uniform(builder, "baseline_functional_severity", 0.05, 0.95)
    builder.add_column(
        dd.SamplerColumnConfig(
            name="patient_reported_burden",
            sampler_type=dd.SamplerType.UNIFORM,
            params=dd.UniformSamplerParams(low=0.0, high=1.0),
            conditional_params={
                "baseline_functional_severity < 0.35": dd.UniformSamplerParams(low=0.0, high=0.55),
                (
                    "baseline_functional_severity >= 0.35 and baseline_functional_severity < 0.70"
                ): dd.UniformSamplerParams(low=0.20, high=0.80),
                "baseline_functional_severity >= 0.70": dd.UniformSamplerParams(low=0.45, high=1.0),
            },
        )
    )
    _conditional_category(
        builder,
        "baseline_comorbidity_burden",
        values=[0, 1, 2, 3, 4],
        weights=[0.24, 0.34, 0.25, 0.12, 0.05],
        conditional={
            "age < 40": ([0, 1, 2, 3, 4], [0.45, 0.35, 0.15, 0.04, 0.01]),
            "age >= 40 and age < 65": ([0, 1, 2, 3, 4], [0.20, 0.35, 0.28, 0.13, 0.04]),
            "age >= 65": ([0, 1, 2, 3, 4], [0.08, 0.23, 0.34, 0.24, 0.11]),
        },
    )
    _conditional_category(
        builder,
        "baseline_treatment_burden",
        values=[0, 1, 2, 3, 4],
        weights=[0.05, 0.25, 0.38, 0.24, 0.08],
        conditional={
            "condition_category == 'oncology'": (
                [0, 1, 2, 3, 4],
                [0.02, 0.10, 0.28, 0.38, 0.22],
            ),
            "condition_category == 'renal'": (
                [0, 1, 2, 3, 4],
                [0.03, 0.16, 0.34, 0.32, 0.15],
            ),
        },
    )
    _category(
        builder,
        "travel_access_burden",
        [0, 1, 2, 3, 4],
        [0.12, 0.28, 0.32, 0.20, 0.08],
    )
    _conditional_category(
        builder,
        "support_availability",
        values=[0, 1, 2, 3, 4],
        weights=[0.06, 0.15, 0.30, 0.31, 0.18],
        conditional={
            "travel_access_burden >= 3": (
                [0, 1, 2, 3, 4],
                [0.16, 0.28, 0.31, 0.18, 0.07],
            ),
            "travel_access_burden < 3": (
                [0, 1, 2, 3, 4],
                [0.04, 0.11, 0.28, 0.35, 0.22],
            ),
        },
    )
    _conditional_category(
        builder,
        "medication_count",
        values=list(range(9)),
        weights=[0.08, 0.14, 0.18, 0.18, 0.15, 0.11, 0.08, 0.05, 0.03],
        conditional={
            "baseline_comorbidity_burden <= 1": (
                list(range(9)),
                [0.15, 0.23, 0.24, 0.18, 0.10, 0.05, 0.03, 0.01, 0.01],
            ),
            "baseline_comorbidity_burden >= 3": (
                list(range(9)),
                [0.01, 0.03, 0.07, 0.12, 0.18, 0.20, 0.18, 0.13, 0.08],
            ),
        },
    )
    return builder


def _enrollments(seed_path: Path) -> dd.DataDesignerConfigBuilder:
    builder = _builder(seed_path)
    _uuid(builder, "research_enrollment_id", "r3-enrollment-")
    _uuid(builder, "patient_snapshot_id", "r3-snapshot-")
    _uuid(builder, "screening_id", "r3-screening-")
    _category(builder, "trial_version", ["r3.1.0"])
    _category(builder, "treatment_arm", ["active", "control"], [0.5, 0.5])
    return builder


def _dose_events(seed_path: Path) -> dd.DataDesignerConfigBuilder:
    builder = _builder(seed_path)
    _uuid(builder, "dose_event_id", "r3-dose-")
    _uniform(builder, "generation_administered_draw", 0.0, 1.0)
    _uniform(builder, "generation_missed_reason_draw", 0.0, 1.0)
    _uniform(builder, "generation_interruption_draw", 0.0, 1.0)
    _expression(
        builder,
        "administered_count",
        "{{ 1 if generation_administered_draw < "
        "(0.96 if generation_adherence_tier == 'low' else "
        "0.80 if generation_adherence_tier == 'high' else 0.90) else 0 }}",
        "int",
    )
    _expression(
        builder,
        "missed_dose_reason",
        "{{ 'access' if "
        "(generation_missed_reason_draw < 0.65 if generation_primary_burden == 'access' "
        "else generation_missed_reason_draw < 0.10 if generation_primary_burden == 'symptoms' "
        "else generation_missed_reason_draw < 0.30) "
        "else 'symptoms' if "
        "(generation_missed_reason_draw < 0.75 if generation_primary_burden in "
        "['access', 'symptoms'] "
        "else generation_missed_reason_draw < 0.55) else 'participant_choice' }}",
        "str",
    )
    _expression(
        builder,
        "treatment_interruption",
        "{{ generation_interruption_draw < (0.01 if administered_count == 1 else 0.10) }}",
        "bool",
    )
    return builder


def _visit_events(seed_path: Path) -> dd.DataDesignerConfigBuilder:
    builder = _builder(seed_path)
    _uuid(builder, "visit_event_id", "r3-visit-")
    _uniform(builder, "generation_visit_status_draw", 0.0, 1.0)
    _uniform(builder, "generation_delay_draw", 0.0, 1.0)
    _expression(
        builder,
        "visit_status",
        "{% if generation_adherence_tier == 'low' %}"
        "{% if generation_visit_status_draw < 0.92 %}completed"
        "{% elif generation_visit_status_draw < 0.95 %}missed{% else %}delayed{% endif %}"
        "{% elif generation_adherence_tier == 'high' %}"
        "{% if generation_visit_status_draw < 0.67 %}completed"
        "{% elif generation_visit_status_draw < 0.85 %}missed{% else %}delayed{% endif %}"
        "{% else %}{% if generation_visit_status_draw < 0.82 %}completed"
        "{% elif generation_visit_status_draw < 0.90 %}missed{% else %}delayed{% endif %}"
        "{% endif %}",
        "str",
    )
    _expression(
        builder,
        "delay_days",
        "{% if visit_status != 'delayed' %}0"
        "{% elif generation_delay_draw < 0.25 %}1"
        "{% elif generation_delay_draw < 0.55 %}2"
        "{% elif generation_delay_draw < 0.78 %}3"
        "{% elif generation_delay_draw < 0.92 %}4{% else %}5{% endif %}",
        "int",
    )
    return builder


def _measurements(seed_path: Path) -> dd.DataDesignerConfigBuilder:
    builder = _builder(seed_path)
    _uuid(builder, "measurement_id", "r3-measurement-")
    _uniform(builder, "generation_observed_draw", 0.0, 1.0)
    _gaussian(builder, "generation_measurement_noise", 0.0, 1.0)
    _expression(
        builder,
        "observed",
        "{{ generation_observed_draw < "
        "(0.98 if generation_adherence_tier == 'low' else "
        "0.86 if generation_adherence_tier == 'high' else 0.94) }}",
        "bool",
    )
    _expression(
        builder,
        "value",
        "{% if generation_measurement_band == 'very_low' %}"
        "{{ 0.10 + 0.05 * generation_measurement_noise }}"
        "{% elif generation_measurement_band == 'low' %}"
        "{{ 0.30 + 0.07 * generation_measurement_noise }}"
        "{% elif generation_measurement_band == 'high' %}"
        "{{ 0.70 + 0.07 * generation_measurement_noise }}"
        "{% elif generation_measurement_band == 'very_high' %}"
        "{{ 0.90 + 0.05 * generation_measurement_noise }}"
        "{% else %}{{ 0.50 + 0.08 * generation_measurement_noise }}{% endif %}",
        "float",
    )
    return builder


def _adverse_events(seed_path: Path) -> dd.DataDesignerConfigBuilder:
    builder = _builder(seed_path)
    _uuid(builder, "adverse_event_id", "r3-adverse-")
    _uniform(builder, "generation_event_present_draw", 0.0, 1.0)
    _uniform(builder, "generation_ae_category_draw", 0.0, 1.0)
    _uniform(builder, "generation_ae_grade_draw", 0.0, 1.0)
    _uniform(builder, "generation_treatment_related_draw", 0.0, 1.0)
    _uniform(builder, "generation_resolved_draw", 0.0, 1.0)
    _uniform(builder, "generation_ae_interruption_draw", 0.0, 1.0)
    _expression(
        builder,
        "event_present",
        "{{ generation_event_present_draw < "
        "(0.04 if generation_ae_risk_tier == 'low' else "
        "0.18 if generation_ae_risk_tier == 'high' else 0.10) }}",
        "bool",
    )
    _expression(
        builder,
        "category",
        "{% if condition_category == 'respiratory' %}"
        "{% if generation_ae_category_draw < 0.20 %}fatigue"
        "{% elif generation_ae_category_draw < 0.30 %}gastrointestinal"
        "{% elif generation_ae_category_draw < 0.45 %}pain"
        "{% elif generation_ae_category_draw < 0.90 %}respiratory{% else %}other{% endif %}"
        "{% elif condition_category == 'oncology' %}"
        "{% if generation_ae_category_draw < 0.35 %}fatigue"
        "{% elif generation_ae_category_draw < 0.60 %}gastrointestinal"
        "{% elif generation_ae_category_draw < 0.82 %}pain"
        "{% elif generation_ae_category_draw < 0.90 %}respiratory{% else %}other{% endif %}"
        "{% else %}{% if generation_ae_category_draw < 0.25 %}fatigue"
        "{% elif generation_ae_category_draw < 0.45 %}gastrointestinal"
        "{% elif generation_ae_category_draw < 0.65 %}pain"
        "{% elif generation_ae_category_draw < 0.85 %}respiratory{% else %}other{% endif %}"
        "{% endif %}",
        "str",
    )
    _expression(
        builder,
        "severity_grade",
        "{% if generation_ae_risk_tier == 'low' %}"
        "{% if generation_ae_grade_draw < 0.82 %}1"
        "{% elif generation_ae_grade_draw < 0.98 %}2{% else %}3{% endif %}"
        "{% elif generation_ae_risk_tier == 'high' %}"
        "{% if generation_ae_grade_draw < 0.52 %}1"
        "{% elif generation_ae_grade_draw < 0.87 %}2{% else %}3{% endif %}"
        "{% else %}{% if generation_ae_grade_draw < 0.70 %}1"
        "{% elif generation_ae_grade_draw < 0.94 %}2{% else %}3{% endif %}{% endif %}",
        "int",
    )
    _expression(
        builder,
        "treatment_related",
        "{{ generation_treatment_related_draw < (0.65 if treatment_arm == 'active' else 0.25) }}",
        "bool",
    )
    _expression(
        builder,
        "resolved",
        "{{ generation_resolved_draw < "
        "(0.92 if severity_grade == 1 else 0.60 if severity_grade == 3 else 0.80) }}",
        "bool",
    )
    _expression(
        builder,
        "treatment_interruption",
        "{{ generation_ae_interruption_draw < "
        "(0.02 if severity_grade == 1 else 0.35 if severity_grade == 3 else 0.12) }}",
        "bool",
    )
    return builder


def _outcomes(seed_path: Path) -> dd.DataDesignerConfigBuilder:
    builder = _builder(seed_path)
    _uuid(builder, "research_outcome_id", "r3-outcome-")
    _uniform(builder, "generation_dropout_draw", 0.0, 1.0)
    _uniform(builder, "generation_dropout_day_draw", 0.0, 1.0)
    _uniform(builder, "generation_dropout_reason_draw", 0.0, 1.0)
    _expression(
        builder,
        "dropout_by_day90",
        "{{ generation_dropout_draw < "
        "(0.08 if generation_dropout_risk_tier == 'low' else "
        "0.35 if generation_dropout_risk_tier == 'high' else "
        "0.55 if generation_dropout_risk_tier == 'very_high' else 0.18) }}",
        "bool",
    )
    _expression(
        builder,
        "dropout_day",
        "{% if generation_dropout_risk_tier == 'low' %}"
        "{{ 50 + 41 * generation_dropout_day_draw }}"
        "{% elif generation_dropout_risk_tier == 'high' %}"
        "{{ 35 + 46 * generation_dropout_day_draw }}"
        "{% elif generation_dropout_risk_tier == 'very_high' %}"
        "{{ 31 + 40 * generation_dropout_day_draw }}"
        "{% else %}{{ 42 + 49 * generation_dropout_day_draw }}{% endif %}",
        "int",
    )
    _expression(
        builder,
        "dropout_reason",
        "{% if generation_primary_dropout_driver == 'adverse_event_burden' %}"
        "{% if generation_dropout_reason_draw < 0.12 %}participant_decision"
        "{% elif generation_dropout_reason_draw < 0.80 %}adverse_event_burden"
        "{% elif generation_dropout_reason_draw < 0.88 %}access_or_travel"
        "{% else %}loss_to_follow_up{% endif %}"
        "{% elif generation_primary_dropout_driver == 'access_or_travel' %}"
        "{% if generation_dropout_reason_draw < 0.15 %}participant_decision"
        "{% elif generation_dropout_reason_draw < 0.23 %}adverse_event_burden"
        "{% elif generation_dropout_reason_draw < 0.88 %}access_or_travel"
        "{% else %}loss_to_follow_up{% endif %}"
        "{% elif generation_primary_dropout_driver == 'loss_to_follow_up' %}"
        "{% if generation_dropout_reason_draw < 0.18 %}participant_decision"
        "{% elif generation_dropout_reason_draw < 0.25 %}adverse_event_burden"
        "{% elif generation_dropout_reason_draw < 0.37 %}access_or_travel"
        "{% else %}loss_to_follow_up{% endif %}"
        "{% else %}{% if generation_dropout_reason_draw < 0.35 %}participant_decision"
        "{% elif generation_dropout_reason_draw < 0.55 %}adverse_event_burden"
        "{% elif generation_dropout_reason_draw < 0.75 %}access_or_travel"
        "{% else %}loss_to_follow_up{% endif %}{% endif %}",
        "str",
    )
    return builder


def build_config(
    table: str,
    seed_path: Path | None = None,
) -> dd.DataDesignerConfigBuilder:
    """Build one NeMo table configuration for the R3 orchestrator."""
    if table == "participants":
        return _participants()
    if seed_path is None:
        raise ValueError(f"{table} requires --seed-path")
    builders = {
        "enrollments": _enrollments,
        "dose_events": _dose_events,
        "visit_events": _visit_events,
        "measurements": _measurements,
        "adverse_events": _adverse_events,
        "outcomes": _outcomes,
    }
    return builders[table](seed_path)


def load_config_builder(
    params: dd.DataDesignerScriptParams | None = None,
) -> dd.DataDesignerConfigBuilder:
    args = _arguments(params)
    return build_config(args.table, args.seed_path)
