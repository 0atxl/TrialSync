# Research integration contract

Status: accepted backend contract with saved-screening frontend integration implemented.

This contract defines how TrialSync's three independent research tools consume the same reviewed
patient, trial, and screening foundation without becoming part of deterministic eligibility:

1. day-30 dropout-risk prediction;
2. DBSCAN cohort context;
3. exact FAISS participant similarity.

The tools share an immutable input context, but they do not invoke one another and one tool's
output never becomes another tool's feature. A user chooses each tool independently from the saved
screening workspace or the dedicated research workspace.

## 1. Trusted entry point

All ingestion paths converge before any research operation:

```text
catalog-aided manual entry ─┐
reviewed text/PDF import ───┼─> Patient + approved facts
manual correction/editing ─┘

approved trial authoring/import -> TrialVersion + ordered criteria

Patient + approved facts -> immutable PatientSnapshot
PatientSnapshot + approved TrialVersion -> deterministic Screening + CriterionEvaluations
```

Groq may propose import candidates, but only reviewed and approved facts or criteria enter the
snapshot and trial version. The clinical-concept catalog supplies controlled identifiers and units.
Neither provider output nor a research model can approve data or change the screening result.

Every research request begins with an authenticated `screening_id`. The server resolves the
following context; clients never submit or remap these identifiers:

```text
owner_id
screening_id
patient_snapshot_id + snapshot_version + content_hash
trial_version_id + version
screening_date + overall_state
engine_version + dsl_version + terminology_version + unit_version
```

The canonical serialization of this context has a `research_context_checksum`. It makes later
enrollment, vector, and prediction records traceable to the exact saved screening without copying
mutable patient or trial state.

## 2. Independent capability contract

| Capability | Required input | Earliest availability | Output | May affect eligibility? |
|---|---|---|---|---|
| Dropout prediction | Research enrollment, baseline snapshot, complete day-30 follow-up snapshot | After the day-30 cutoff | Probability, threshold, band, horizon, model version, contributions | No |
| Cohort context | Saved screening and active cohort run | Immediately after a screening is saved | Reference-cluster association or unassigned state, projection context, cluster summaries | No |
| Similarity | Saved screening and active exact index | Immediately after a screening is saved | Ranked reference participants, cosine scores, transparent differences | No |

The dropout tool is longitudinal. Screening alone does not imply enrollment and cannot answer the
day-30-to-day-90 question. Cohort and similarity tools use screening-time facts and evidence
patterns; they do not require enrollment or follow-up data.

Similarity does not measure how much care a participant needs. It identifies comparable records
under a declared representation so a user can inspect how similar cases differ. Dropout probability
is the separate retention-attention signal. Cohort context may help organize follow-up review, but
cluster membership is not a priority score, diagnosis, or recommendation.

## 3. Platform-owned longitudinal enrollment contract

The accepted 4,000-row R3 dataset is training and evaluation lineage only. Its checksum remains in
the model manifest to identify the model's origin, but its rows and identifiers are not runtime
participants and are never selected or linked by a user.

Runtime data is created inside TrialSync from a saved screening. The user selects **Start research
follow-up**; the server generates the enrollment identifier and copies the immutable context. No R3
or R6 artifact identifier appears in the UI or request.

### `research_enrollments`

One row represents one versioned participant-trial episode:

| Field | Contract |
|---|---|
| `id` | Server-generated UUID |
| `owner_id` | Authenticated owner |
| `screening_id` | Unique immutable link to the canonical screening |
| `patient_snapshot_id` | Must equal the screening snapshot |
| `trial_version_id` | Must equal the screening trial version |
| `research_context_checksum` | Hash of the resolved immutable context |
| `enrollment_date` | Day-0 origin |
| `observation_cutoff_day` | `30` for the current contract |
| `prediction_horizon_day` | `90` for the current contract |
| `baseline_values_json` | Validated enrollment baseline snapshot |
| `baseline_sources_json` | Explicit source for every baseline value |
| `baseline_snapshot_hash` | Canonical values-and-sources checksum |
| `feature_contract_version` | Exact R5 input contract |
| `tracking_status` | `active` or `closed`; not a model feature |
| `created_by_id`, `created_at` | Immutable provenance |

The baseline snapshot contains the 12 model baseline features. Values owned by the screening are
server-derived:

- condition category from the approved trial context;
- age at screening and sex from the immutable patient snapshot;
- present-condition burden and medication count from snapshot facts.

Enrollment-only values are requested once when unavailable:

- site region and treatment arm;
- baseline functional severity and reported burden;
- baseline treatment burden;
- travel/access burden and support availability.

Every value keeps its source. Missing values remain missing and block feature-snapshot creation.
Categorical values are resolved through a versioned mapping registry. If a saved screening uses a
condition, site, or treatment value outside the model's frozen vocabulary, the risk capability
returns `unsupported_model_input`; the user is never asked to disguise it as a known category.

## 4. Complete longitudinal event schema

Events are append-only. A correction creates a replacement row with `supersedes_event_id`, actor,
reason, and timestamp; it never edits evidence used by an existing follow-up snapshot or prediction.
All event tables include `id`, `owner_id`, `research_enrollment_id`, `event_day`, `source_label`,
optional `source_document_id`, `recorded_by_id`, `recorded_at`, and optional correction metadata.

### `research_dose_events`

One row represents one scheduled dose opportunity or bounded daily dose interval:

```text
medication_concept    controlled concept identifier
scheduled_date
scheduled_count       integer >= 1
administered_count    integer between 0 and scheduled_count
dose_amount           optional positive numeric value
dose_unit             required when dose_amount is present
route                 optional controlled value
status                scheduled | administered | partially_administered | missed | held
reason                required for missed or held when known
```

`missed_count` is derived as `scheduled_count - administered_count`; it is not manually entered.
Day-30 `missed_dose_rate` is total missed divided by total scheduled. No scheduled doses is an
explicit incomplete state, not a zero missed-dose rate.

### `research_visit_events`

One row represents one scheduled visit:

```text
visit_type             controlled protocol/local visit type
scheduled_date
completed_date        nullable
status                scheduled | completed | delayed | missed
delay_days            derived and validated; nullable for missed/scheduled
reason                 required for delayed or missed when known
```

The feature builder derives delayed-visit count, missed-visit rate, and mean visit delay. No
scheduled visits is incomplete rather than zero missed visits.

### `research_measurements`

One row represents one follow-up measurement:

```text
concept               controlled concept identifier
value_numeric
unit                   required compatible unit
observed               explicit boolean; false keeps a missing observation distinct from zero
observed_date
method                 optional
reference_range        optional structured lower/upper bounds and unit
```

The current dropout contract consumes `functional_severity`. The builder derives latest severity,
baseline-to-latest slope, observation count, and measurement missingness. Other approved
measurements may be stored but are not silently added to the frozen model feature schema.

### `research_adverse_events`

One row represents one recorded adverse event:

```text
event_concept          controlled concept identifier or reviewed coded term
onset_date
severity_grade        integer 1..4
resolved_date         nullable
serious                boolean
relatedness            unrelated | unlikely | possible | probable | definite | unknown
action_taken           optional controlled value
outcome                ongoing | resolved | resolved_with_sequelae | unknown
```

The feature builder derives adverse-event count and summed burden through day 30. No recorded
events is zero only when the source explicitly confirms that absence; an unreviewed safety record
is missing.

### `research_follow_up_snapshots`

One immutable row is produced from baseline plus non-superseded events through the declared cutoff:

| Field | Contract |
|---|---|
| `research_enrollment_id` | Parent episode |
| `cutoff_day` | `30` |
| `feature_schema_version` | Exact ordered 22-feature schema |
| `feature_values_json` | Validated baseline and derived follow-up values |
| `feature_sources_json` | Source/provenance for every value |
| `feature_snapshot_hash` | Canonical checksum |
| `event_set_checksum` | Hash of contributing event IDs and versions |
| `missing_features_json` | Explicit unresolved fields |
| `status` | `incomplete` or `ready` |
| `created_at` | Version timestamp |

Creating new events produces a new follow-up snapshot. Existing predictions retain the snapshot
hash they used and are never recalculated in place.

Outcomes, withdrawal state, generated risk tiers, and post-cutoff events are excluded from the
feature builder.

## 5. Dropout prediction contract

The model package records separate provenance boundaries:

```text
model_artifact_checksum       exact XGBoost binary
training_dataset_checksum     exact 4,000-row R3 training/evaluation lineage
feature_schema_checksum       exact ordered runtime feature contract
feature_snapshot_hash         one platform enrollment at one cutoff
```

The runtime loads only the model package and the selected platform follow-up snapshot. It never
looks up a training-dataset row.

Prediction creation requires a `ready` follow-up snapshot, validates package/database metadata,
and stores:

- enrollment, follow-up snapshot, and model-version foreign keys;
- probability, candidate-specific stored threshold, and versioned band;
- day-30 cutoff and day-90 horizon;
- native XGBoost Tree SHAP contributions grouped to original features;
- immutable input hash and disclaimer version.

## 6. Saved-screening-to-R6 projection contract

The approved 750-member V3.1 run remains the stable reference landscape. It supplies reproducible
clusters, core samples, preprocessing, and exact-index members. A platform patient is an external
query overlay; it is not silently inserted into the frozen cohort and does not change any cluster
or neighbor relationship.

### Patient-fact projection

The server:

1. resolves the immutable patient snapshot from `screening_id`;
2. maps only concepts declared by the active representation;
3. validates or normalizes units using the frozen unit contract;
4. represents present, absent, unknown, and missing distinctly;
5. uses the saved evidence dates and demographic fields;
6. applies the active run's frozen medians, means, scales, and L2 normalization;
7. records context, feature-order, preprocessing, and vector checksums.

New catalog concepts remain visible in the ordinary patient record but are reported as outside the
active representation. They never create a new dimension implicitly.

### Screening-profile projection

The server:

1. resolves the same immutable snapshot;
2. loads the active run's fixed 20 reference trial versions and ordered criteria;
3. calls the exact pure deterministic screening engine for each trial in memory;
4. does not create 20 ordinary screening-history rows;
5. maps pass, fail, and unknown into the frozen 314-dimensional order;
6. applies the active preprocessing and records all version/checksum metadata.

The user's originally selected trial does not have to be one of the 20 reference trials. Changing
the reference panel requires an explicitly rebuilt and versioned R6 run.

## 7. DBSCAN live-context contract

Standard DBSCAN has no native prediction method for unseen points. TrialSync must not imply that a
platform patient was part of the original fit.

The active run will therefore publish its original core-member mapping and a versioned
out-of-sample association rule:

1. transform the query with the frozen representation preprocessing;
2. find original core members within the selected `eps`;
3. if none exist, return `unassigned`;
4. if one cluster is represented, return `associated` with that neutral cluster label;
5. if multiple clusters are represented, select the nearest core member with deterministic tie
   handling and return the competing labels;
6. return distance, rule version, and an explicit `out_of_sample: true` marker.

The PCA artifact must store its fitted mean/components so the external query can be shown as a
display-only overlay. PCA position never determines the association.

For follow-up management, the Atlas may overlay owner-scoped enrollment status and day-30
completeness as filters or table columns. Those operational fields are not clustering features.

## 8. FAISS live-query contract

The exact index accepts the externally projected unit vector and returns reference members in
descending cosine similarity. It does not require a cohort `member_id` and does not modify the
index.

Results include:

- query screening and representation versions;
- ranked reference member IDs and labels;
- cosine similarity;
- human-readable top feature differences;
- for screening-profile features, trial title, criterion wording, result state, and canonical
  missing/evidence category;
- statement that similarity is not eligibility evidence or a care recommendation.

## 9. API contract

### Overview aggregate

```text
GET /api/v1/overview
```

The owner-scoped application Overview combines complete deterministic eligibility counts, a
bounded daily screening-activity series, dropout workflow counts for potentially eligible
screenings, prioritized attention items, and compact recent-screening summaries. Dropout states are
`not_started`, `information_needed`, `ready`, and `predicted`; they are resolved through immutable
screening-to-enrollment linkage. The aggregate does not persist duplicate dashboard state or change
eligibility. If the configured risk artifact cannot be validated, `dropout.status` is `degraded`
while the core eligibility, activity, attention, and recent-screening content remains available.

### Shared capability discovery

```text
GET /api/v1/research/screenings/{screening_id}/capabilities
```

Returns three independent states:

```json
{
  "dropout_prediction": {"status": "needs_enrollment", "action": "start_follow_up"},
  "cohort_context": {"status": "ready", "representations": ["patient_fact", "screening_profile"]},
  "similarity": {"status": "ready", "representations": ["patient_fact", "screening_profile"]}
}
```

### Enrollment and events

```text
POST /api/v1/research/screenings/{screening_id}/enrollment
GET  /api/v1/research/enrollments/{enrollment_id}
GET  /api/v1/research/enrollments/{enrollment_id}/events
POST /api/v1/research/enrollments/{enrollment_id}/dose-events
POST /api/v1/research/enrollments/{enrollment_id}/visit-events
POST /api/v1/research/enrollments/{enrollment_id}/measurements
POST /api/v1/research/enrollments/{enrollment_id}/adverse-events
POST /api/v1/research/enrollments/{enrollment_id}/follow-up-snapshots
GET  /api/v1/research/enrollments/{enrollment_id}/follow-up-snapshots
```

### Independent research actions

```text
POST /api/v1/research/risk/predictions
POST /api/v1/research/screenings/{screening_id}/cohort-context
POST /api/v1/research/screenings/{screening_id}/similarity
```

Risk requests identify a platform `enrollment_id` and follow-up snapshot. Cohort/similarity
requests identify a representation and neighbor bound under a path-authorized platform
`screening_id`; the server selects and reports the configured active run.
Existing cohort-member endpoints remain available for reference-Atlas exploration.

Follow-up snapshot creation explicitly confirms whether dose, visit, measurement, and adverse-event
records are complete through day 30. A confirmation never supplies a numeric value: zero is derived
only where an empty but reviewed record has a defined zero meaning. Missing dose/visit denominators
and absent functional measurements remain incomplete.

## 10. UX contract

The saved-screening workspace presents one **Research tools** region with three independent
actions:

```text
Retention risk       Cohort context        Similar participants
Day-30 readiness     Reference association Exact nearest records
[Open]               [Explore]             [Find similar]
```

Opening one tool does not run or reveal the others.

### Retention risk

- If no enrollment exists: show **Start research follow-up**.
- Prefill screening-owned baseline values and request only unresolved enrollment fields.
- Present event entry in four sections: doses, visits, functional measurements, adverse events.
- Ask for observable counts/events; derive rates on the server.
- Collapse complete inputs into a provenance summary.
- Enable prediction only when the day-30 snapshot is ready.
- Show probability, threshold, horizon, model version, and top contributions beside the unchanged
  eligibility summary.

### Cohort context

- Deep-link to the dedicated Atlas with the current saved screening as an external overlay.
- Allow patient-fact and screening-profile switching.
- Show associated neutral cluster or unassigned state, nearby core members, noise, cluster size,
  and out-of-sample explanation.
- Allow operational filters for follow-up completeness without adding them to the vector.

### Similar participants

- Permit a compact drawer from the saved screening and a detailed view in the Atlas.
- Show representation, exact cosine score, and readable differences.
- Never label similarity as level of care, eligibility, or predicted outcome.

## 11. Implemented backend bridge

The backend integration implements the following bridge before frontend wiring:

1. retain model-version and prediction concepts;
2. replace artifact-row enrollment lookup with platform-generated research enrollments;
3. add dose, visit, measurement, adverse-event, and follow-up-snapshot tables;
4. separate training-dataset provenance from runtime input provenance;
5. revise prediction creation to use a follow-up-snapshot foreign key;
6. add capability discovery so the frontend never guesses state;
7. extend R6 artifacts with frozen transform/core/PCA metadata;
8. add external-screening projection, DBSCAN association, and external-vector FAISS queries;
9. resolve screening-profile UUID dimensions into canonical human-readable evidence metadata.

The coordinated saved-screening frontend now exposes all three independent actions, enrollment and
event capture, explicit day-30 readiness, XGBoost/SHAP results, out-of-sample cohort association,
and exact cosine neighbors. The configured V3.1 run is readable through the live query bridge. A
population-wide Cohort Atlas and Trial Recruitment Overview are available as linked research
workspace routes. Saved-screening cohort and similarity results can open the Atlas with the same
screening and representation selected, while participant-level actions remain independently usable
in the screening detail. No compatibility layer or training-row mapping is required.

## 12. Acceptance tests

- Manual entry and an approved import producing the same facts yield the same immutable snapshot,
  patient-fact vector, and deterministic screening result.
- No client supplies patient-snapshot, trial-version, training-row, or cohort-member mappings when
  starting follow-up from a screening.
- Enrollment foreign keys and context checksum match the canonical screening.
- Event corrections are append-only and cannot alter an existing follow-up snapshot.
- Dose and visit rates are server-derived with explicit zero-denominator incomplete states.
- Missing day-30 values never become zero.
- No post-cutoff event or outcome enters the feature snapshot.
- Fixed enrollment/events reproduce the same feature hash, probability, and contributions.
- Prediction creation leaves the screening and criterion evaluations byte-for-byte unchanged.
- The three capability states are independent; one unavailable tool does not disable the others.
- Saved-screening patient-fact projection matches direct frozen-contract construction.
- Screening-profile projection agrees with 20 direct pure-engine evaluations and creates no
  ordinary screening rows.
- External FAISS neighbors match brute-force cosine search.
- DBSCAN live context uses only frozen core members and declares out-of-sample association.
- New catalog concepts are reported but do not mutate a frozen vector schema.
- Risk, outcome, SHAP, chat, and RAG data never enter R6 vectors.
- Cross-owner screening, enrollment, event, cohort, and similarity access is rejected.
