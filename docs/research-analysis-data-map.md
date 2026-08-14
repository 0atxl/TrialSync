# Research analysis data map

This guide explains which TrialSync dataset is used for dropout prediction, SHAP explanation,
patient clustering, and similarity search. It is a reading companion to the authoritative
[research-extension implementation plan](../agent-docs/research-extension-implementation-plan.md),
not a replacement for it.

## One project, two research datasets

TrialSync intentionally uses two separate synthetic datasets because dropout prediction and
patient similarity answer different questions.

| Analysis | Dataset | Unit represented by one row/vector | Current status |
|---|---|---|---|
| Dropout prediction | R3 longitudinal enrollment dataset | One trial enrollment at the day-30 landmark | 4,000-row experiment generated and awaiting final acceptance |
| SHAP explanation | R3 model-ready dropout features | One model prediction for one enrollment | Planned in R4 |
| DBSCAN clustering | R6 screening-derived patient cohort | One unique synthetic patient | Planned in R6 |
| FAISS similarity | R6 screening-derived patient cohort | One patient vector in one frozen representation | Planned in R6 |

```text
R3 longitudinal enrollments
  -> landmark_day30_features.parquet
  -> dropout model
  -> SHAP explanations

R6 unique synthetic patients × fixed trial panel
  -> patient-fact vectors ---------> DBSCAN + FAISS
  -> screening-profile vectors ----> DBSCAN + FAISS
```

## R3: dropout prediction data

The dropout model uses the R3 longitudinal dataset. Its primary training input is
`landmark_day30_features.parquet`, with one row per synthetic enrollment and features available
through day 30. The target is `dropout_by_day90`.

Example model features include:

- baseline and latest functional severity;
- treatment, travel/access, comorbidity, medication, and patient-reported burden;
- support availability;
- scheduled, administered, and missed doses;
- scheduled, completed, delayed, and missed visits;
- adverse-event count and burden;
- measurement observations and missingness.

Outcome details, events after day 30, hidden generator tiers, and random sampler draws are not
model inputs. The accepted 400-enrollment demo is suitable for pipeline demonstrations; the
4,000-enrollment experiment cohort will be used for the primary model comparison.

### Reading guide: the three R3 modeling views

The three views below are derived from the same seven longitudinal source tables:

```text
participants, enrollments, dose events, visit events, measurements,
adverse events, and outcomes
```

They are different time-based representations of the same synthetic enrollment histories. They
are not three independent datasets that must be joined into one model. The first model experiment
uses only `landmark_day30_features.parquet`; the other two views support later analyses.

| View | One row represents | Prediction or analysis question | Intended significance |
|---|---|---|---|
| `landmark_day30_features.parquet` | One enrollment at day 30 | Will dropout occur during days 31–90? | Primary fixed-horizon classification view for the BTech model comparison. |
| `dynamic_landmarks.parquet` | One enrollment at a configured prediction landmark | Will dropout occur in the next 30 days? | Supports rolling risk updates as new visits, doses, or measurements arrive. |
| `survival_features.parquet` | One enrollment | How long until dropout, or until observation is censored? | Preserves event timing for future time-to-event or survival analysis. |

#### Fixed day-30 landmark

The day-30 view creates one feature row per enrollment. Every predictor must be available on or
before day 30, so the model sees a frozen snapshot of the participant's observed history:

```text
history through day 30 -> feature row -> dropout_by_day90
```

`dropout_by_day90` is the target, not a predictor. A value of `true` means that dropout occurred
during days 31–90; `false` means that dropout did not occur by day 90. At inference time, the
future outcome is unknown and the trained model returns a probability of dropout by day 90.

#### Dynamic landmarks

The dynamic view can contain multiple rows for one enrollment. Each row uses information only up
to its own `prediction_day` and labels whether dropout occurs in the following 30-day window:

```text
history through prediction_day -> dropout_in_next_30_days
```

This is useful for a future scenario in which risk is recalculated after a new missed dose or visit.
Because one enrollment can appear repeatedly, train/validation/test assignment must remain grouped
by participant; rows must not be split independently at random.

#### Survival view

The survival view stores time-to-event information instead of reducing every outcome to a single
yes/no label. Its key fields are `time_to_dropout_or_censor_days` and `event_observed`:

```text
dropout on day 58 -> time = 58, event_observed = true
no dropout by day 90 -> time = 90, event_observed = false
```

This distinguishes an early dropout from a late dropout and represents participants who complete
the observation window without an event. It is intended for a later survival-analysis extension,
not the initial Logistic Regression, XGBoost, and LightGBM classification comparison.

#### Recommended project order

1. Train and evaluate the initial models with `landmark_day30_features.parquet`.
2. Use SHAP on the selected model using the same day-30 feature representation.
3. Present `dynamic_landmarks` as the rolling-prediction extension.
4. Present `survival_features` as the time-to-event extension, implementing it only if the project
   schedule permits.

## R4: SHAP explanations

SHAP does not require another generated dataset. It explains the selected trained dropout model
using the same feature representation supplied to that model.

Two explanation levels are planned:

- **Global explanation:** summarizes which features generally have the largest influence across
  the evaluated cohort.
- **Local explanation:** shows which features pushed one enrollment's predicted risk higher or
  lower relative to the model's reference output.

Examples might show that missed-dose rate, missed visits, limited support, or adverse-event burden
influenced a prediction. This describes model behavior only. A SHAP contribution is not proof that
a feature caused dropout, and it is never an eligibility score.

## R6: screening-derived cohort data

Clustering and similarity do not use the R3 dropout dataset. R6 will create a separate cohort of:

- 750 unique synthetic patient snapshots;
- a fixed panel of 20 approved synthetic trial versions;
- 15,000 deterministic patient × trial evaluations;
- one final patient-level sample for each of the 750 patients.

The 15,000 evaluations provide screening evidence patterns. They are collapsed into 750 patient
representations before clustering or indexing, so frequently evaluated patients are not counted as
additional people.

### Patient-fact representation

This representation describes what is recorded about the patient:

- age band and approved demographic fields;
- condition and medication assertions;
- normalized compatible observations;
- evidence age;
- missingness indicators.

It supports the question:

> Which patients have similar recorded fact profiles?

### Screening-profile representation

This representation describes how the same patient evaluates across the fixed trial panel:

- one-hot `pass`, `fail`, and `unknown` criterion results;
- result rates by trial and criterion family;
- missing-information categories;
- screening-result patterns across the reference trials.

`unknown` receives its own representation and is never treated as halfway between pass and fail.
This supports the question:

> Which patients produce similar eligibility-evidence patterns across the same trials?

## DBSCAN clustering

DBSCAN will run independently in patient-fact space and screening-profile space. It groups dense
regions of each feature space and may leave unusual patients labelled as noise. Cluster labels will
use neutral names such as `fact_cluster_0`; they are not diagnoses or clinical phenotypes.

A seeded two-dimensional PCA projection may be displayed in the Cohort Atlas, but clustering will
operate on the complete feature vectors rather than the simplified display coordinates.

## FAISS similarity indexing

FAISS will build one exact CPU cosine-similarity index for each representation:

1. patient-fact similarity index;
2. screening-profile similarity index.

A result will include the neighboring patient identifiers, similarity values, and a transparent
comparison of the facts or criterion states that made them similar. The query patient is excluded
from its own result list. Similarity is a research navigation aid, not screening evidence or a
recommendation that two patients should enter the same trial.

## Separation rules

The R6 clustering and similarity vectors must not contain:

- actual or synthetic dropout outcomes;
- dropout-model probabilities or risk bands;
- SHAP values;
- hidden generator tiers or random draws;
- chat messages;
- RAG or LLM summaries.

Keeping these fields out prevents the model's output from defining patient similarity and keeps
the cohort experiment independent from dropout prediction.

## Reading the final results

When these phases are complete, interpret each output as follows:

| Output | Safe interpretation | Unsafe interpretation |
|---|---|---|
| Dropout probability | Model-estimated risk in the synthetic R3 task | Real clinical dropout probability |
| SHAP contribution | Feature contribution to this model's output | Cause of dropout |
| DBSCAN cluster | Dense group in a documented synthetic feature space | Medical phenotype or diagnosis |
| FAISS neighbor | Similar vector under one frozen representation | Eligibility evidence or treatment recommendation |

The deterministic TrialSync screening engine remains the only source of the stored eligibility
result. Dropout predictions, explanations, clusters, and neighbors cannot change it.
