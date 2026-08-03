# NeMo Data Designer Guide: Synthetic Trial Dropout Dataset

This guide proposes a first synthetic dataset for participant-level clinical-trial
dropout prediction. It is a schema and generation plan for an academic prototype,
not a clinically validated data-generating process.

The proposed first experiment uses NVIDIA NeMo Data Designer for structured
synthetic attributes and a controlled Python step for longitudinal visits and
dropout outcomes. The resulting tables can be used directly to train the
dropout model.

## Important design decision

The dataset should not be one wide row containing the participant's entire trial
future. That would make it impossible to tell what was known at prediction time.

Use four related tables:

```text
participants.csv       one row per participant at baseline
visits.csv             one row per participant per scheduled visit or interval
adverse_events.csv     one row per adverse event, optional for the first version
model_landmarks.csv    one row per prediction time and used for model training
```

The first baseline model can use one row per participant from
`model_landmarks.csv`. The later dynamic model can use one row per participant
per visit.

## 1. Participant baseline table

One row represents one enrolled participant.

| Field | Type | Keep | Why it should exist |
|---|---|---:|---|
| `participant_id` | String | Yes | Uniquely identifies a participant and prevents duplicate records. |
| `trial_id` | String | Yes | Identifies the trial in which the participant is enrolled. |
| `trial_version` | Integer | Yes | Preserves which protocol version produced the participant's data. |
| `site_id` | String | Yes | Allows site-level effects and participant-level train/test splitting. |
| `treatment_arm` | Category | Yes | Treatment assignment may affect adverse events, burden, and dropout risk. |
| `screening_date` | Date | Yes | Defines when baseline information became available. |
| `enrollment_date` | Date | Yes | Defines the participant's time origin in the trial. |
| `planned_trial_duration_days` | Integer | Yes | Defines the maximum follow-up period. |
| `age_years` | Integer | Yes | Represents age as a continuous predictor. |
| `age_band` | Category | Optional | Makes age effects easier to interpret and model nonlinearly. |
| `sex` | Category | Yes | Allows demographic analysis and fairness checks. |
| `condition_burden` | Integer, 0–5 | Yes | Represents the complexity of the participant's condition. |
| `baseline_disease_severity` | Float, 0–10 | Recommended | Represents initial disease severity before treatment begins. |
| `comorbidity_count` | Integer | Recommended | More comorbidities may increase burden and dropout risk. |
| `treatment_burden` | Integer, 0–5 | Yes | Represents complexity or difficulty of the treatment regimen. |
| `concurrent_medication_count` | Integer | Recommended | More medications may increase complexity and side-effect risk. |
| `visit_frequency_per_4_weeks` | Integer | Yes | Frequent visits increase time and travel burden. |
| `travel_distance_km` | Float | Yes | Travel difficulty may increase missed visits and dropout. |
| `site_type` | Category | Yes | Academic, community, urban, or rural sites may have different retention patterns. |
| `required_procedures_count` | Integer | Yes | More procedures increase participant burden. |
| `support_availability` | Category | Yes | Family, transport, financial, or coordinator support may reduce dropout risk. |
| `baseline_adherence_tendency` | Float, 0–1 | Yes | Represents the participant's expected ability to follow the protocol. |
| `prior_missed_appointment_rate` | Float, 0–1 | Recommended | Provides a baseline behavioral adherence signal. |
| `baseline_symptom_burden` | Integer, 0–10 | Optional | More symptoms may reduce tolerance for continuing participation. |
| `generation_cohort` | String | Metadata | Identifies which synthetic generation run created the participant. |
| `generation_seed` | Integer | Metadata | Makes the synthetic dataset reproducible. |

For the first version, keep all fields marked Yes and add Recommended fields if
the generated data remains manageable.

## 2. Visit-level table

One row represents one scheduled visit or one visit interval for one participant.

| Field | Type | Keep | Why it should exist |
|---|---|---:|---|
| `participant_id` | String | Yes | Links the visit to the participant. |
| `trial_id` | String | Yes | Links the visit to the trial. |
| `visit_number` | Integer | Yes | Identifies the participant's position in the trial timeline. |
| `visit_day` | Integer | Yes | Represents time since enrollment without relying only on dates. |
| `scheduled_date` | Date | Yes | Preserves the planned clinical timeline. |
| `visit_status` | Category | Yes | Distinguishes completed, missed, rescheduled, and withdrawn visits. |
| `visit_delay_days` | Integer | Recommended | Measures how late the participant attended. |
| `dose_scheduled_count` | Integer | Yes | Records how many doses were expected during the interval. |
| `dose_taken_count` | Integer | Yes | Records how many scheduled doses were taken. |
| `missed_dose_count` | Integer | Yes | Directly supports the future missed-dose risk scenario. |
| `missed_dose_rate` | Float, 0–1 | Yes | Normalizes missed doses across different dose schedules. |
| `missed_dose_reason` | Category | Recommended | Separates forgetting, adverse events, travel, access, and side effects. |
| `current_disease_severity` | Float, 0–10 | Recommended | Allows disease status to change over time. |
| `current_treatment_burden` | Integer, 0–5 | Recommended | Captures treatment burden changes during the trial. |
| `adverse_event_count` | Integer | Yes | Measures the number of adverse events in the interval. |
| `maximum_adverse_event_severity` | Integer, 0–3 | Yes | Captures whether adverse events were mild or severe. |
| `treatment_related_adverse_event` | Boolean | Recommended | Indicates whether an event may be related to study treatment. |
| `treatment_interruption` | Boolean | Yes | Records whether treatment was paused because of an event. |
| `support_contact_count` | Integer | Recommended | Measures coordinator or support interactions. |
| `days_since_last_completed_visit` | Integer | Yes | Represents current engagement with the study. |
| `active_at_visit` | Boolean | Metadata | Indicates whether the participant was still active at that point. |

The visit table is essential for dynamic prediction. Without it, the model
cannot learn how dropout risk changes after missed doses or adverse events.

## 3. Adverse-event table

This table is optional for the first rough version. Visit-level event counts are
enough for the first model, but this table supports later safety analysis.

| Field | Type | Keep | Why it should exist |
|---|---|---:|---|
| `event_id` | String | Optional | Uniquely identifies the adverse event. |
| `participant_id` | String | Optional | Links the event to the participant. |
| `visit_number` | Integer | Optional | Identifies when the event occurred. |
| `onset_day` | Integer | Optional | Places the event on the trial timeline. |
| `event_category` | Category | Optional | Distinguishes fatigue, nausea, pain, infection, and other event types. |
| `severity` | Integer, 1–3 | Optional | Represents event seriousness. |
| `related_to_treatment` | Boolean | Optional | Allows treatment-related events to affect dropout risk differently. |
| `resolved_before_next_visit` | Boolean | Optional | Indicates whether the event persisted. |
| `caused_dose_interruption` | Boolean | Optional | Connects adverse events to missed doses. |
| `led_to_withdrawal` | Boolean | Analysis only | Records whether the event directly caused dropout. |

## 4. Outcome table

One row represents the final observed outcome for one participant.

| Field | Type | Keep | Why it should exist |
|---|---|---:|---|
| `participant_id` | String | Yes | Links the outcome to the participant. |
| `dropout_event` | Boolean | Yes | Main binary target: whether the participant dropped out. |
| `dropout_date` | Date or null | Yes | Records when dropout occurred. |
| `dropout_day` | Integer or null | Yes | Makes time-to-event calculations easier. |
| `dropout_reason` | Category | Analysis only | Helps analyze why participants left but must not be a model input. |
| `trial_completed` | Boolean | Analysis only | Indicates whether the participant reached the planned endpoint. |
| `last_observed_day` | Integer | Yes | Records the last time the participant was observed. |
| `event_observed` | Boolean | Yes | Required for survival analysis: 1 means dropout was observed, 0 means censored. |
| `censoring_reason` | Category | Analysis only | Explains why a non-dropout participant stopped being observed. |
| `censoring_date` | Date or null | Yes | Records when follow-up ended without an observed dropout. |

## 5. Model-ready landmark table

This is the table used directly for model training. A landmark is a prediction
time, such as baseline or the end of week 4.

For the first baseline model, create one row per participant. For the dynamic
model, create one row per participant per completed visit.

| Field | Type | Keep | Why it should exist |
|---|---|---:|---|
| `participant_id` | String | Yes | Identifies the participant. |
| `prediction_day` | Integer | Yes | Defines when the prediction was made. |
| `age_years` | Integer | Yes | Baseline demographic feature. |
| `sex` | Category | Yes | Baseline demographic feature. |
| `condition_burden` | Integer | Yes | Baseline clinical burden feature. |
| `treatment_burden` | Integer | Yes | Baseline treatment complexity feature. |
| `visit_frequency_per_4_weeks` | Integer | Yes | Baseline logistical burden feature. |
| `travel_distance_km` | Float | Yes | Baseline access difficulty feature. |
| `baseline_adherence_tendency` | Float | Yes | Baseline adherence feature. |
| `support_availability` | Category | Yes | Baseline support feature. |
| `required_procedures_count` | Integer | Yes | Baseline trial burden feature. |
| `completed_visits_to_date` | Integer | Dynamic only | Measures observed engagement. |
| `missed_visits_to_date` | Integer | Dynamic only | Measures accumulated attendance problems. |
| `scheduled_doses_to_date` | Integer | Dynamic only | Provides the denominator for adherence. |
| `missed_doses_to_date` | Integer | Dynamic only | Measures accumulated dose non-adherence. |
| `missed_dose_rate_to_date` | Float | Dynamic only | Normalizes dose adherence across participants. |
| `recent_missed_doses_14d` | Integer | Dynamic only | Captures recent deterioration in adherence. |
| `adverse_events_to_date` | Integer | Dynamic only | Measures cumulative safety burden. |
| `recent_adverse_events_14d` | Integer | Dynamic only | Captures recent safety changes. |
| `severe_adverse_events_to_date` | Integer | Dynamic only | Separates serious events from minor events. |
| `treatment_interruptions_to_date` | Integer | Dynamic only | Measures treatment disruption. |
| `days_since_last_completed_visit` | Integer | Dynamic only | Measures recent engagement. |
| `support_contacts_to_date` | Integer | Dynamic only | Represents ongoing support interaction. |
| `dropout_in_next_30_days` | Boolean | Dynamic target | Supports short-term participant-risk prediction. |
| `dropout_by_trial_end` | Boolean | Baseline target | Supports fixed-horizon participant-level prediction. |
| `time_to_dropout_or_censor_days` | Integer | Survival target | Supports time-to-event modelling. |
| `event_observed` | Boolean | Survival target | Distinguishes observed dropout from censoring. |

## 6. Fields that must not be model inputs

These fields are useful for analysis but cause target leakage if they are known
only after the prediction time:

```text
dropout_date
dropout_reason
trial_completed
led_to_withdrawal
censoring_reason
future_missed_doses
future_adverse_events
future_visit_status
latent_dropout_risk
```

The rule is:

```text
Every feature must be known on or before prediction_day.
```

## 7. Suggested first synthetic trial configuration

These are adjustable synthetic starting assumptions, not clinical facts:

| Setting | Initial value |
|---|---:|
| Participants | 1,000 |
| Sites | 10 |
| Trial duration | 84 days |
| Visits | Weekly |
| Dose schedule | 7 scheduled doses per week |
| Initial dropout rate | 15–25% |
| Age range | 18–80 |
| Maximum travel distance | 150 km |
| Maximum condition burden | 5 |
| Maximum treatment burden | 5 |
| Maximum required procedures | 6 |
| Dynamic prediction horizon | 30 days |
| Missing-dose scenarios | Low, medium, and high adherence |

Generate 1,000 participants first. Increase to 5,000–10,000 only after the
schema and model pipeline work.

## 8. NeMo Data Designer setup

The current NVIDIA package is called **NeMo Data Designer**. It can be used as
a Python library or through other NVIDIA surfaces. The official quick start
uses the `data-designer` package, an NVIDIA API key, `DataDesigner`, and a
`DataDesignerConfigBuilder`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install data-designer pandas pyarrow

export NVIDIA_API_KEY="your-key"
data-designer config list
```

See the [official getting-started guide](https://docs.nvidia.com/nemo/datadesigner/getting-started/welcome)
for installation, provider configuration, preview, and workflow execution.

For this dataset, use these column types:

| NeMo feature | Use in this project |
|---|---|
| Category sampler | Sex, site type, treatment arm, support availability, and dose-miss reason. |
| Uniform or Gaussian sampler | Age, distance, burden scores, and adherence scores. |
| Poisson sampler | Number of adverse events or missed visits. |
| Datetime sampler | Screening, enrollment, and scheduled dates. |
| Expression column | Derived values such as age band and adherence rate. |
| Custom Python logic | Visit expansion, dose simulation, dropout labels, and survival time. |
| Validation column | Checks for impossible or inconsistent records. |
| LLM-structured column | Optional narrative fields only; not required for the first dataset. |

The [NeMo column documentation](https://docs.nvidia.com/nemo/datadesigner/concepts/columns)
describes sampler, expression, structured, seed, and validation column types.
Statistical samplers are preferable here because the core dataset is numeric and
categorical rather than narrative.

## 9. Starter NeMo configuration

This creates a small participant baseline preview. Add the remaining baseline
columns after confirming that the first rows look sensible.

```python
import data_designer.config as dd
from data_designer.interface import DataDesigner

designer = DataDesigner()
builder = dd.DataDesignerConfigBuilder()

builder.add_column(
    dd.SamplerColumnConfig(
        name="sex",
        sampler_type=dd.SamplerType.CATEGORY,
        params=dd.CategorySamplerParams(
            values=["female", "male", "not_recorded"],
            weights=[0.48, 0.48, 0.04],
        ),
    )
)

builder.add_column(
    dd.SamplerColumnConfig(
        name="age_years",
        sampler_type=dd.SamplerType.UNIFORM,
        params=dd.UniformSamplerParams(low=18, high=80),
        convert_to="int",
    )
)

builder.add_column(
    dd.SamplerColumnConfig(
        name="condition_burden",
        sampler_type=dd.SamplerType.CATEGORY,
        params=dd.CategorySamplerParams(
            values=[0, 1, 2, 3, 4, 5],
            weights=[0.05, 0.15, 0.25, 0.25, 0.20, 0.10],
        ),
    )
)

builder.add_column(
    dd.SamplerColumnConfig(
        name="treatment_burden",
        sampler_type=dd.SamplerType.CATEGORY,
        params=dd.CategorySamplerParams(
            values=[0, 1, 2, 3, 4, 5],
            weights=[0.05, 0.15, 0.25, 0.25, 0.20, 0.10],
        ),
    )
)

builder.add_column(
    dd.SamplerColumnConfig(
        name="travel_distance_km",
        sampler_type=dd.SamplerType.UNIFORM,
        params=dd.UniformSamplerParams(low=1, high=150),
    )
)

builder.add_column(
    dd.SamplerColumnConfig(
        name="baseline_adherence_tendency",
        sampler_type=dd.SamplerType.UNIFORM,
        params=dd.UniformSamplerParams(low=0.2, high=0.98),
    )
)

builder.add_column(
    dd.SamplerColumnConfig(
        name="support_availability",
        sampler_type=dd.SamplerType.CATEGORY,
        params=dd.CategorySamplerParams(
            values=["none", "low", "medium", "high"],
            weights=[0.10, 0.25, 0.45, 0.20],
        ),
    )
)

designer.validate(builder)

preview = designer.preview(builder, num_records=20)
preview.display_sample_record()

results = designer.create(
    builder,
    num_records=1000,
    dataset_name="synthetic_dropout_baseline",
)
```

If a sampler name or parameter differs in the installed version, inspect the
available configuration with:

```python
builder.info.display("samplers")
```

The official tutorial demonstrates category samplers, weighted values, uniform
values, validation, `preview()`, and `create()`. See the
[NeMo Data Designer basics tutorial](https://docs.nvidia.com/nemo/datadesigner/tutorials/the-basics)
for the current API examples.

## 10. Generating visits and dropout labels

Do not ask the LLM to independently decide whether a participant dropped out.
That can create inconsistent labels. Generate baseline attributes with NeMo,
then use a controlled Python function or processor to create visits, dose
events, adverse events, and outcomes.

Conceptually, dropout risk should increase with:

```text
condition burden
treatment burden
travel distance
missed-dose rate
adverse-event severity
missed visits
```

Dropout risk should decrease with:

```text
support availability
baseline adherence tendency
completed visits
```

A rough nonlinear hazard score could be:

```text
risk_score =
    -3.0
    + 0.35 * condition_burden
    + 0.30 * treatment_burden
    + 0.015 * travel_distance_km
    + 1.20 * missed_dose_rate
    + 0.45 * recent_adverse_events
    + 0.50 * missed_visits_to_date
    - 0.45 * support_score
    - 0.80 * baseline_adherence_tendency
    + 0.75 * interaction(missed_dose_rate, treatment_burden)
```

Convert the score to a probability using:

```text
dropout_probability = 1 / (1 + exp(-risk_score))
```

At each visit interval:

1. Generate the scheduled visit and dose counts.
2. Generate missed doses using baseline adherence, travel, burden, and support.
3. Generate adverse events using treatment burden and treatment arm.
4. Update cumulative and recent features.
5. Calculate the current dropout probability.
6. Sample whether dropout occurs.
7. Stop generating future visits after dropout.

The coefficient values are synthetic assumptions for experimentation, not
clinical evidence. Keep them in a versioned configuration file so that each
dataset can be reproduced.

NeMo Data Designer supports custom Python logic and validation workflows. If a
custom column or processor is not convenient in the installed environment,
generate the participant table with NeMo, export it, and run the visit/outcome
step as a normal Python post-processing script. The resulting tables are still
the dataset used for model training. See the
[official validator documentation](https://docs.nvidia.com/nemo/datadesigner/concepts/validators)
for local callable and validation-column patterns.

## 11. Validation before model training

Check the following before training:

- No duplicate `participant_id` values exist in the participant table.
- Every visit belongs to an existing participant.
- Visit dates are ordered correctly.
- No visits occur after dropout.
- `missed_dose_count <= dose_scheduled_count`.
- `dropout_day <= planned_trial_duration_days`.
- Participants who complete the trial have `dropout_event = 0`.
- Participants with `dropout_event = 1` have `event_observed = 1`.
- The dropout rate is not extremely low or high.
- The dropout rate increases when missed doses increase.
- Adverse events increase treatment interruption.
- Support availability reduces missed visits.
- Train, validation, and test sets contain different participants.

The most important relationship checks are:

```text
missed-dose rate ↑       → predicted dropout risk ↑
adverse-event severity ↑ → predicted dropout risk ↑
support availability ↑   → predicted dropout risk ↓
```

## 12. Model-training views

Create these views from the generated tables.

### Baseline fixed-horizon view

One row per participant with features available at enrollment and the target:

```text
dropout_by_trial_end
```

This is the first model to implement.

### Dynamic landmark view

One row per participant per prediction visit with features accumulated only up to
that visit and the target:

```text
dropout_in_next_30_days
```

This supports the missed-dose scenario.

### Survival view

One row per participant with:

```text
time_to_dropout_or_censor_days
event_observed
```

This supports survival analysis and correctly handles participants whose final
outcome is not observed.

Split all views by `participant_id`, never by individual visit rows.

## 13. Initial model comparison

Use the generated data to compare:

1. Majority-class baseline.
2. Logistic regression baseline.
3. Random forest or gradient boosting model.
4. Survival model for time-to-dropout.

Evaluate with AUROC, AUPRC, recall, calibration/Brier score, and survival
metrics where applicable. Because the dataset is synthetic, also test whether
the model recovers the relationships deliberately placed into the generator.

## 14. Recommended first version

Start with:

```text
1,000 participants
84-day trial
weekly visit rows
weekly aggregated dose information
adverse-event counts and severity
baseline dropout target
dynamic 30-day dropout target
survival time and censoring fields
```

Do not add narrative medical notes or LLM-generated explanations in the first
dataset. They are not needed for dropout prediction and may introduce noise.

The proposed first output should be:

```text
participants.parquet
visits.parquet
outcomes.parquet
model_landmarks.parquet
generation_config.json
validation_report.json
```

NeMo also supports seed datasets if a legitimate public or aggregate source
becomes available. A seed dataset is optional; the initial version can be
generated from the samplers above. See the
[official seed-data tutorial](https://docs.nvidia.com/nemo/datadesigner/tutorials/seeding-with-an-external-dataset)
for the seed workflow.
