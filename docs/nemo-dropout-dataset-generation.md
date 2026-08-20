# Synthetic longitudinal trial-dropout dataset

This document defines the R3 Track A dataset for TrialSync. It is a versioned,
auditable synthetic research dataset for fixed-horizon dropout-risk experiments,
not a clinically validated data-generating process and not evidence about real
trial participants. Reproducibility here means preserving the exact configuration,
run metadata, and frozen artifacts; it does not mean claiming a byte-identical
regeneration from an unavailable project-level sampler seed.

NVIDIA NeMo Data Designer is the generation tool for this project.
TrialSync may perform a later schema/chronology validation pass, but NeMo must
not be asked to invent eligibility states or real clinical ground truth. The
synthetic dropout label is explicitly defined by a reviewed NeMo uniform draw and
dependent expression and is never presented as a clinical fact.

## Current implementation status

R3 is complete; its data contract and local generation path are validated. The
accepted 20-enrollment smoke cohort contains 4 synthetic dropouts (20%). The accepted
400-enrollment demo cohort contains 64 synthetic dropouts (16%) with 280/60/60
train/validation/test rows. Both runs produced seven linked source tables and three derived views
with zero LLM/model requests.

The accepted 4,000-enrollment experiment contains 702 synthetic dropouts (17.55%)
and a 2,800/600/600 train/validation/test split. Its EDA, feature dictionary, dataset card, linkage
manifest, leakage audit, checksums, and workflow diagram are complete. R4 subsequently used the
frozen day-30 landmark view to compare dummy, logistic-regression, XGBoost, and LightGBM models,
with bootstrap uncertainty, SHAP, and local MLflow tracking. The authoritative sequence remains the R3 section of
the [research-extension implementation plan](../agent-docs/research-extension-implementation-plan.md#phase-r3--synthetic-longitudinal-dropout-protocol).

Accepted artifact row counts:

| Output | 20-row smoke | 400-row demo | 4,000-row experiment |
|---|---:|---:|---:|
| `research_participants` | 20 | 400 | 4,000 |
| `research_enrollments` | 20 | 400 | 4,000 |
| `research_dose_events` | 1,692 | 34,018 | 339,849 |
| `research_visit_events` | 227 | 4,546 | 45,428 |
| `research_measurements` | 494 | 9,892 | 98,856 |
| `research_adverse_events` | 19 | 408 | 3,920 |
| `research_outcomes` | 20 | 400 | 4,000 |
| `landmark_day30_features` | 20 | 400 | 4,000 |
| `dynamic_landmarks` | 100 | 2,000 | 20,000 |
| `survival_features` | 20 | 400 | 4,000 |

## Research references and design influence

The public [Brunalos clinical-trials-ml repository](https://github.com/brunalos/clinical-trials-ml)
describes a vaccine-clinical-trial dropout project. It gathers study-level
information through ClinicalTrials.gov/AACT-style sources, merges records by
`nct_id`, performs missing-value handling, encoding, scaling, and train/test
splitting, and compares classical models including decision trees, random forests,
KNN, linear regression, and XGBoost. Its README describes trial duration, phase,
participant count, demographics, geography, sponsors, treatment information, and
adverse-event summaries as useful predictors or analysis fields.

That repository influenced TrialSync in three ways:

- retain trial context, site/region, treatment-arm, protocol-burden, and provenance
  fields rather than generating anonymous rows;
- keep preprocessing and participant-level splitting explicit and reproducible;
- treat dropout prediction as a research analysis rather than an eligibility result.

TrialSync deliberately differs in one important way: it generates participant-level
longitudinal events and a declared day-30-to-day-90 target. Brunalos's repository is
used as a methodological reference, not copied data, a label source, or external
validation evidence.

The dataset review also examined MIMIC-III, PRO-ACT, n2c2, NCT02054715-D1, and
Project Data Sphere. MIMIC-III, PRO-ACT, n2c2, and Project Data Sphere have access
terms or data-use restrictions; NCT02054715-D1 currently provides a useful
study-specific dictionary and paper but not the participant rows needed for public
training. None is a runtime or clean-reproduction dependency. Those constraints are reflected in
the active research plan's data boundary.

## R3 time and outcome contract

Each research enrollment has one fixed time origin:

| Name | Meaning |
|---|---|
| `enrollment_day` | Day 0 and the beginning of the simulated trial episode. |
| `observation_cutoff_day` | Day 30; predictors may use information through this day only. |
| `prediction_horizon_day` | Day 90; the primary target is dropout during days 31–90. |
| `dropout_day` | Generated day on which the participant leaves, when observed. |
| `censor_day` | Last observed day when dropout is not observed. |

The primary model task is therefore:

> Use features available through day 30 to predict whether dropout occurs by day 90.

The model predicts an individual probability. The cohort dropout rate is an
aggregate descriptive statistic, not the target for an individual row.

The 90-day outcome is retained. Removing it would remove the future label needed to
evaluate dropout prediction. R3 also derives dynamic-landmark and survival views for future
experiments, but those model families are not required for the first fixed-horizon model.

## Seven logical source tables

The tables below are source-of-truth event tables. The model does not consume all
seven tables directly; a deterministic feature-building step creates one or more
model-ready views from them.

```text
seven source tables
        -> chronology, linkage, and leakage checks
        -> landmark_day30_features
        -> dropout_by_day90 model
```

All longitudinal event rows are keyed by `research_enrollment_id`, not only by
participant ID. This preserves the trial context if a synthetic participant is ever
associated with more than one trial episode.

### 1. `research_participants`

One row per fictional person and static baseline attributes:

| Field group | Examples |
|---|---|
| Identity | `research_participant_id`, linked `research_enrollment_id`, `dataset_split` |
| Demographics | age or age band, sex |
| Condition | condition category, disease category, baseline severity |
| Burden | comorbidity burden, treatment burden, travel/access burden |
| Support | support availability, site/region category |

Values are fictional and remain condition-aware. The first R3 release uses documented
`normalized_0_1` condition-marker values rather than claiming clinically calibrated eGFR,
HbA1c, tumour-burden, or respiratory-function units. A later condition-specific protocol may
add raw-unit fields, but those fields must never be treated as interchangeable across conditions.

### 2. `research_enrollments`

One row per participant–trial episode. This is the immutable bridge to TrialSync:

| Field | Purpose |
|---|---|
| `research_enrollment_id` | Stable longitudinal episode identifier |
| `research_participant_id` | Links to the fictional participant |
| `patient_snapshot_id` | Synthetic immutable-snapshot identifier used by the generation contract |
| `trial_version_id` | Fixed synthetic condition-trial protocol identifier |
| `screening_id` | Synthetic identifier reserved for later product-link materialization |
| `screening_state` | `potentially_eligible`, computed by the canonical domain engine |
| `enrollment_day` | Fixed day-0 origin |
| `observation_cutoff_day` | Locked to 30 in the primary task |
| `prediction_horizon_day` | Locked to 90 in the primary task |
| `treatment_arm`, `site_region` | Assigned arm and copied immutable site context |

The offline generator creates typed synthetic patient/trial inputs and calls the pure
`trialsync.domain.screen` engine before generating longitudinal events. It records the resulting
state and engine version, but it does not call the HTTP/service layer or create PostgreSQL patient,
trial, or screening rows. The 400-row product linkage may be materialized later in R5 using the
ordinary service boundary. Screening state never becomes the dropout label.

For physical export, every participant baseline field is copied into this enrollment row as an
immutable snapshot. This intentional denormalization makes each trial episode self-contained and
is validated against the participant table. The artifact must therefore not be described as fully
normalized.

### 3. `research_dose_events`

One row per scheduled dose or dose interval:

`research_enrollment_id`, event day, scheduled count, administered count, missed
count, missed-dose reason, and optional treatment interruption.

This table supports adherence features and the missed-dose Scenario Lab. A scenario
may change a pre-cutoff dose event and recompute every dependent feature, but it does
not rewrite the observed outcome label.

### 4. `research_visit_events`

One row per scheduled visit or visit interval:

`research_enrollment_id`, visit number, visit day, scheduled date, visit status
(`completed`, `missed`, or `delayed`), and delay days. Withdrawal belongs to the outcome and
censoring contract rather than becoming a duplicate visit-status label.

Visit-level dose counts are not duplicated here; dose information belongs in
`research_dose_events`.

### 5. `research_measurements`

Long-form observations rather than a wide collection of condition-specific columns:

`measurement_id`, `research_enrollment_id`, `measurement_day`, `measurement_name`, normalized
`value`, `unit`, `observed`, and `dataset_split`.

The first implementation may generate only severity, treatment burden, and one or
two normalized laboratory-style measures. More measurements are not useful unless
their generation assumptions and feature use are documented.

### 6. `research_adverse_events`

One row per simulated event:

`adverse_event_id`, `research_enrollment_id`, `event_day`, category, severity grade,
treatment-related flag, resolved flag, treatment-interruption flag, and `dataset_split`.

An event that directly causes withdrawal is an outcome-analysis field. It must not be
used as a predictor when it is only known after the prediction cutoff.

### 7. `research_outcomes`

One row per enrollment containing labels and follow-up status:

| Field | Meaning |
|---|---|
| `dropout_by_day90` | Primary fixed-horizon binary target |
| `dropout_day` | Observed generated dropout day, or null |
| `dropout_reason` | Synthetic analysis taxonomy, not a feature |
| `event_observed` | Whether dropout was observed |
| `censor_day` | Last known follow-up without observed dropout |

Outcome fields are joined to a model view only as targets or evaluation metadata.

## Model-ready views

Views are deterministic transformations of the seven source tables. They need not
be separately simulated.

### Baseline fixed-horizon view: `landmark_day30_features`

In this project, “baseline fixed-horizon” means one prediction row per enrollment
at the locked day-30 cutoff. It does not mean that every feature must come from
day 0. Features may be accumulated from enrollment through day 30, while the target
looks forward to day 90.

One row per enrollment, using only event rows with `event_day <= 30`:

```text
research_enrollment_id
baseline_functional_severity
latest_functional_severity
functional_severity_slope
missed_dose_count
missed_dose_rate
missed_visit_count
adverse_event_count
measurement_observation_count
measurement_missingness_rate
feature_cutoff_day
dropout_by_day90
dataset_split
```

`dropout_day`, `dropout_reason`, post-day-30 events, and final completion status
must not be included as model features.

### Dynamic landmark view: `dynamic_landmarks`

The R3 artifact creates one row per eligible enrollment and prediction day at days 7, 14, 21,
28, and 30. Each row aggregates only events up to that prediction day and uses the following
contract. Training a dynamic model remains optional after the primary R4 fixed-horizon model:

```text
research_enrollment_id
prediction_day
features_known_through_prediction_day
dropout_in_next_30_days
target_observed
dataset_split
```

For example, a day-30 row predicts dropout during days 31–60. Participants who have
already dropped out before a landmark are not eligible for that landmark row. A
landmark is retained when dropout is observed inside its next-30-day target window or
when follow-up covers the complete window. Otherwise it is excluded; incomplete
follow-up must never be silently treated as a negative label.

### Survival view: `survival_features`

One row per enrollment containing:

```text
research_enrollment_id
time_to_dropout_or_censor_days
event_observed
censor_day
dataset_split
```

`event_observed = true` means an observed dropout event occurred; false means the
row is censored under the declared follow-up rule. The view is generated with R3, while
survival-model experiments remain optional and are not required for the first R4 model.

All views must use participant-level splits before model fitting. Every enrollment for one
participant follows that participant into the same split; individual enrollments or event rows
must never be split independently.

## Frozen physical contract

[`backend/research/schemas/r3_dataset.py`](../backend/research/schemas/r3_dataset.py) is the
machine-readable source of truth for every ordered Parquet column. Its contract version is
`r3-dataset-contract-v1`, and it covers exactly seven source tables plus three derived views. It
also freezes `site_region` as the site-context field, the immutable enrollment-snapshot columns,
forbidden model fields, hidden-tier probabilities, per-column provenance, and the schema
fingerprint.

New runs write the contract version, unique generation-run ID, UTC timestamp, schema fingerprint,
physical-layout declaration, and provenance map into generation metadata. The accepted 20- and
400-row artifacts predate those added metadata fields; their observed reports are preserved rather
than retrospectively assigning invented run identifiers.

## Generation process

1. Ask NeMo Data Designer to sample fictional participants, trial contexts, and baseline attributes.
2. Create typed synthetic patient-snapshot and trial-version inputs in memory.
3. Run the exact deterministic domain screening engine and retain only potentially eligible
   synthetic enrollment linkages; do not imply that database rows were persisted.
4. Generate scheduled visits and dose events.
5. Ask NeMo Data Designer to sample measurements, missingness, adverse events, and
   the dropout random draw; reviewed dependent expressions convert the draws and seed context into
   event fields and the synthetic outcome.
6. Apply deterministic censoring so event rows do not continue after dropout or
   the declared follow-up horizon.
7. Derive model views from the source events.
8. Validate distributions, chronology, linkage, leakage, and splits; create checksums when the
   accepted artifact is packaged.

No NVIDIA API key is required for this recipe. The selected R3 configuration contains only
statistical sampler and expression columns, so Data Designer executes the calculations locally on
the machine's CPU, records zero LLM/model usage, and consumes no hosted-model tokens. Provider
aliases shown by `data-designer config list` are available configurations, not evidence that a
provider was called.

Install the pinned research dependency and confirm the package/configuration before a run:

    backend/.venv/bin/python -m pip install -e './backend[dev,research]'
    backend/.venv/bin/data-designer config list
    backend/.venv/bin/pip show data-designer

For linked downstream tables, Data Designer 0.8 evaluates each statistical draw first and then
evaluates expression columns against both that draw and the relational seed row. The accepted
configuration uses dependent expressions, rather than sampler parameters that read a seed-dataset
column, to encode those reviewed relationships.

The configuration is table-aware. Preview the participant table first:

    backend/.venv/bin/data-designer validate backend/research/configs/r3_nemo.py
    backend/.venv/bin/data-designer preview backend/research/configs/r3_nemo.py --num-records 20 --non-interactive -- --table participants

After reviewing the participant preview, run a small end-to-end smoke cohort. This exercises all
seven source tables and all three views. Use a new output directory for a new run; do not overwrite
an accepted artifact:

    backend/.venv/bin/python backend/research/generate_r3_nemo.py --num-records 20 --output artifacts/nemo/r3_smoke

Review `artifacts/nemo/r3_smoke/validation_report.json` before creating the demo cohort. The
accepted 400-enrollment artifact was created with:

    backend/.venv/bin/python backend/research/generate_r3_nemo.py --num-records 400 --output artifacts/nemo/r3_demo

The 4,000-enrollment review candidate and its freeze evidence were created with:

    backend/.venv/bin/python backend/research/generate_r3_nemo.py --num-records 4000 --output artifacts/nemo/r3_experiment_4000
    backend/.venv/bin/python backend/research/analyze_r3_dataset.py artifacts/nemo/r3_experiment_4000 --summary-output backend/research/reports/r3_experiment_4000_observed.json

The aggregate review report is checked in at
`backend/research/reports/r3_experiment_4000_observed.json`; participant-level Parquet files and
the full local approval package remain ignored under `artifacts/`.

The orchestrator calls NeMo Data Designer for seven logical table configurations. For the
4,000-row cohort, the participant configuration runs as ten bounded 400-row batches to avoid a
Data Designer 0.8.0 async-scheduler wait; all batches use the same frozen samplers. Enrollment,
event, and outcome configurations then use their linked seed tables. The orchestrator writes the
seven source Parquet tables and the three
documented derived views. Running `data-designer create` directly on the config
only creates the table selected by `--table`; it is not the complete R3 run.

The ownership boundary is explicit:

| NeMo Data Designer generates | TrialSync shapes and validates |
|---|---|
| IDs, baseline categories/ranges, treatment arms | relational seed rows and fixed day-0/weekly schedules |
| dose administration and missed-dose reasons | in-memory canonical screening state and artifact foreign-key checks |
| visit status and delays | censoring after dropout or day 90 |
| measurement missingness and values | participant-level splits and leakage-safe views |
| adverse-event presence, category, grade, and flags | chronology, range, label, and consistency validation |
| dropout random draws plus dependent label, day, and reason expressions | Parquet export and validation report |

The Python layer is therefore orchestration/relational shaping, not a second
offline statistical generator. The model label is produced inside Data Designer by a uniform
sampler draw and the reviewed tier-dependent expression in `r3_nemo.py`.

The generated directory contains a `_nemo_runs/` subdirectory with NeMo's run
artifacts. Do not commit the generated directory; `artifacts/` is ignored by Git.

The generator must not export its hidden dropout-risk points or tier as model
features. They exist only while NeMo samples the probabilistic label and are removed
from the seven exported source tables and three model views.

## Locked cohort sizes and assumptions

| Cohort | Size | Current state | Purpose |
|---|---:|---|---|
| Smoke cohort | 20 enrollments | Accepted: 4 dropouts (20%) | End-to-end command and artifact check |
| Tiny characterization run | 50 enrollments | Accepted: 11 dropouts (22%) | Credential-free protocol check |
| Demo cohort | 400 enrollments | Accepted: 64 dropouts (16%) | Product-facing research demo |
| Experiment cohort | 4,000 enrollments | Accepted: 702 dropouts (17.55%) | Completed R4 model comparison and stress evaluation |

The generator does not force an exact cohort prevalence. It applies the frozen hidden-tier
probabilities to independently sampled uniform draws and reports the resulting event count for
each run and split. The observed 16% demo prevalence is therefore a generated result—not model
accuracy, a failed 25% requirement, or an empirical clinical estimate. The 4,000-row artifact must
be inspected and reported on its own terms without tuning the held-out test set after inspection.

The condition portfolio is metabolic, cardiovascular, renal, oncology, and
respiratory. Generator coefficients, schedules, missingness rules, dropout reasons,
and censoring rules must be versioned in `generation_config.json` before model tuning.

### Frozen BTech-scale causal assumptions

These are transparent artificial assumptions designed to produce a useful academic
modeling problem. They are not estimates of real clinical-trial behaviour.

| Generated relationship | Reviewed assumption |
|---|---|
| Trial context | Five shared synthetic trial versions, one for each condition category; participants do not receive unique one-person trials. |
| Patient-reported burden | Correlated with baseline functional severity. |
| Comorbidity and medications | Older age shifts comorbidity upward; greater comorbidity shifts medication count upward. |
| Dose adherence and visits | Travel burden, limited support, treatment burden, and patient-reported burden increase missed-dose and missed-visit probability. |
| Measurements | All condition markers use a documented `normalized_0_1` scale; values depend on baseline severity, treatment arm, and time with bounded Gaussian noise. |
| Measurement missingness | Observation probability depends on the same reviewed adherence tier, so missingness is feature-dependent rather than claimed to be completely random. |
| Adverse events | Probability and grade depend on baseline severity, comorbidity, medication count, and treatment burden. |
| Dropout | NeMo samples a uniform random draw and a reviewed expression compares it with the probability for a hidden multi-factor tier built only from baseline and day-30-observable variables. |

The hidden dropout tiers use frozen probabilities of `0.08`, `0.18`, `0.35`, and
`0.55` for low, moderate, high, and very-high artificial risk. Thresholding creates
a deliberately nonlinear joint effect: combinations of burden and adherence factors can cross
a tier boundary even when one factor alone does not. This supports comparison of logistic
regression with tree models. The exact generated prevalence is always reported and is never forced
to equal a predetermined percentage.

The primary training input remains `landmark_day30_features.parquet`. Do not train
directly on `research_outcomes.parquet`, and do not include identifiers,
`dataset_split`, `dropout_reason`, censoring fields, or hidden generator metadata as
features.

## NeMo Data Designer generation route

Data Designer is the required generation tool for the current R3 BTech workflow. Record the
package version, evaluated configuration, local execution/model-usage summary, output location,
and validation results.

Suitable NeMo responsibilities include:

- category, uniform, Gaussian, Poisson, and datetime sampling;
- dependent expressions such as age bands;
- schema validation and previews;
- optional fictional narrative fields, excluded from the first model.

Data Designer creates one tabular output per generation run. The R3 orchestrator
therefore executes seven linked NeMo runs: participants, enrollments, dose events,
visit events, measurements, adverse events, and outcomes. TrialSync supplies each
downstream run with the previously generated identifiers and fixed event schedule,
then performs censoring, relational validation, and view derivation. It does not
replace those NeMo-generated values with a separate simulator.

NeMo should generate the synthetic fields and any declared fictional narrative
fields. The target definition, table keys, chronology checks, and leakage checks
must remain explicit and documented. Do not send controlled external rows or
row-derived prompts to a hosted provider unless the source terms explicitly
permit it.

See the [NeMo getting-started guide](https://docs.nvidia.com/nemo/datadesigner/getting-started/welcome),
[column documentation](https://docs.nvidia.com/nemo/datadesigner/concepts/columns), and
[validator documentation](https://docs.nvidia.com/nemo/datadesigner/concepts/validators).

## Required validation

- The Data Designer run configuration and package metadata are recorded; because
  the sampler-and-expression recipe does not currently expose a project seed through the
  Data Designer 0.8 CLI, reproducibility is tracked by preserving the exact
  configuration and artifact metadata rather than claiming identical checksums
  from a seed flag.
- IDs are unique and event foreign keys resolve.
- Event dates follow the declared ordering.
- No events occur after dropout or censoring.
- Dose counts and rates are mathematically consistent.
- Every enrollment resolves to one internally consistent synthetic snapshot/trial/screening
  identifier set and a potentially eligible canonical domain-engine result; database resolution is
  not claimed before R5 materialization.
- No post-cutoff event becomes a model feature.
- Dropout labels agree with event times and censoring.
- Train, validation, and test participants do not overlap.
- The missed-dose scenario recomputes every dependent adherence feature.
- The model view passes schema and range checks.
- The Data Designer run succeeds locally and records zero LLM/model requests for the
  sampler-and-expression configuration.
- NeMo output passes the same invariant checks.

## Versioned artifacts

The end-to-end generator writes the seven source tables, three derived views,
`generation_config.json`, `validation_report.json`, and the `_nemo_runs/` evidence directory.
The accepted R3 package also includes the linkage manifest, feature dictionary, dataset card, and
checksums listed below. These review documents are frozen exit evidence; their names in this list
do not imply that the initial smoke command creates them.

```text
research_participants.parquet
research_enrollments.parquet
research_dose_events.parquet
research_visit_events.parquet
research_measurements.parquet
research_adverse_events.parquet
research_outcomes.parquet
landmark_day30_features.parquet
dynamic_landmarks.parquet
survival_features.parquet
generation_config.json
linkage_manifest.json
feature_dictionary.md
validation_report.json
dataset_card.md
checksums.json
```

The 400-enrollment demo linkage may be materialized in TrialSync. The 4,000-enrollment
experiment cohort remains a versioned research artifact with a reproducibility
manifest, not bulk ordinary screening history.

Pause for review of the generated dataset card, feature dictionary, leakage audit,
prevalence, and validation report before implementing model experiments.
