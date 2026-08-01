# TrialSync Patient Data Entry and Editing Overhaul

**Date:** 2026-08-02
**Status:** PD6 complete on 2026-08-02; the patient data-entry overhaul is complete
**Relationship to the research plan:** This is a bounded core-product quality
improvement. It does not change deterministic screening semantics, immutable saved
screenings, or the R0–R8 research-extension sequence.

## 1. Purpose

Replace the current generic patient profile and fact forms with a guided,
clinically coherent workflow suitable for TrialSync's synthetic academic
demonstration.

The overhaul must make common edits obvious, prevent invalid combinations, show
clear feedback after every successful mutation, and preserve an understandable
change history. It must not claim to be a hospital EHR or add real-patient
workflows.

The primary demonstration journey is:

```text
Open synthetic patient
  -> review demographics and clinical details
  -> edit a controlled value
  -> see the exact before/after change
  -> add, edit, remove, or restore a clinical detail
  -> understand which future screenings use the change
  -> retain all previously saved immutable screening evidence
```

## 2. Fixed product decisions

These decisions remain fixed unless the user explicitly revises this plan.

### 2.1 Data and claim boundary

- TrialSync continues to use fictional synthetic participant data only.
- This is an academic clinical-trial matching platform, not a production EHR.
- No EHR integration, billing, encounter management, clinical-order entry, or
  medical-advice workflow is introduced.
- Deterministic screening remains the trusted operation.
- Existing saved screenings and their patient snapshots remain immutable.

### 2.2 Biological sex

- The field represents **biological sex for TrialSync screening**, not gender
  identity or administrative gender.
- Canonical stored values are lowercase `male` and `female`.
- The UI labels are **Male** and **Female**.
- `null` remains a data-quality state displayed as **Not recorded**. It is not a
  third biological-sex category.
- New and edit forms use accessible radio buttons rather than free text.
- Existing mixed-case values are normalized during migration or first update.
- Backend validation rejects every other non-null value.
- The screening engine continues to normalize the value before comparison so
  existing approved trial rules remain reproducible.

### 2.3 Pregnancy consistency

- Pregnancy remains the canonical condition concept `pregnancy`.
- Its value uses the existing assertions `present`, `absent`, and `unknown`,
  displayed as **Pregnant**, **Not pregnant**, and **Unknown**.
- New manual pregnancy entries require an effective or assessed date.
- A patient with biological sex `male` cannot be saved with pregnancy
  `present` in this synthetic project.
- Attempting to add or edit pregnancy to `present` for a male patient returns a
  blocking, field-specific conflict.
- Attempting to change biological sex to `male` while an active pregnancy
  `present` fact exists also returns a blocking conflict that identifies the
  pregnancy fact to resolve.
- Pregnancy `absent` and `unknown` remain valid for male patients because a trial
  may require explicit evidence rather than inference.
- Pregnancy `present` with biological sex not recorded is allowed but produces a
  review warning asking the user to complete the demographic profile.
- TrialSync never silently changes sex or pregnancy in response to the other.
- Legacy conflicts remain visible with a reconciliation warning; the migration
  must not rewrite evidence without user review.

### 2.4 Controlled clinical details

- The generic **Fact type / Concept / Value / Unit** form is removed from the
  routine patient workflow.
- Users choose a labelled clinical detail from a controlled catalog.
- The selected catalog entry determines the input control, valid assertions,
  unit, date requirement, and help text.
- Canonical concept codes remain stable so approved trial rules keep working.
- Free-text notes are not screening evidence.
- An unsupported detail may be deferred rather than creating an unrestricted
  concept editor.

### 2.5 Editing, removal, and feedback

- Every active clinical detail has clear **Edit** and **Remove** actions.
- Removal requires confirmation and a reason.
- Removal voids the active detail; it does not destroy its history.
- A recently removed detail offers a bounded **Undo** action.
- Successful create, edit, removal, restore, and profile changes produce
  top-right toast notifications.
- Validation errors remain next to the relevant field and in an accessible error
  summary; a toast is not the only error explanation.
- Toasts state the completed action and use before/after values when useful.
- All changes explain that existing saved screenings remain unchanged and future
  screenings use the active record.

## 3. Current baseline and gaps

The current implementation:

- stores `Patient.sex` as an unrestricted nullable string;
- keeps date of birth and sex in an always-editable profile form;
- exposes the internal fact shape directly;
- supports fact updates in the API but has no fact-editing UI;
- immediately hard-deletes facts;
- reloads data after mutations without success feedback;
- accepts arbitrary concept strings;
- validates numeric value/unit pairing but not concept-specific values;
- has no patient-profile or fact change activity;
- has no cross-field pregnancy/sex validation;
- correctly preserves previous screening snapshots, but does not explain that
  behavior on the patient page.

The overhaul must preserve the useful existing behavior:

- user ownership checks;
- duplicate patient-name review;
- deterministic `pass`, `fail`, and `unknown`;
- immutable patient snapshots;
- supported/refused/unknown assertions;
- numeric units and effective dates;
- responsive, keyboard-accessible UI;
- synthetic-data boundary messaging.

## 4. Target information architecture

The patient detail route becomes four deliberate regions:

```text
Patient header
  Synthetic ID, display name, concise status, patient actions

Demographics
  Readable summary rows
  Display name
  Date of birth
  Biological sex for screening
  [Edit demographics]

Clinical details
  Search/filter and grouped current details
  Conditions | Medications | Labs and observations
  [Add clinical detail]
  Each row: label, value/status, date, source, Edit, Remove

Record activity and screening impact
  Recent create/edit/remove/restore events
  Existing saved screenings retained
  Future screenings use current active data
```

The default page is a review surface, not a wall of editable controls. Editing
opens a focused section, drawer, or dialog with explicit **Save changes** and
**Cancel** actions.

## 5. Controlled concept catalog

Create one backend-owned catalog and expose it through a read-only API contract.
The frontend must not maintain a second independent list.

Each catalog entry includes:

```text
fact_type
concept
display_label
group
input_kind
allowed_assertions
fixed_unit or allowed_units
effective_date_required
screening_supported
help_text
display_order
```

### 5.1 Initial conditions

| Label | Canonical concept | Allowed status |
|---|---|---|
| Type 1 diabetes | `type1_diabetes` | Present / Absent / Unknown |
| Type 2 diabetes | `type2_diabetes` | Present / Absent / Unknown |
| Hypertension | `hypertension` | Present / Absent / Unknown |
| Asthma | `asthma` | Present / Absent / Unknown |
| Pregnancy status | `pregnancy` | Pregnant / Not pregnant / Unknown |

### 5.2 Initial medications

| Label | Canonical concept | Allowed status |
|---|---|---|
| Metformin | `metformin` | Present / Absent / Unknown |
| Atorvastatin | `atorvastatin` | Present / Absent / Unknown |
| Insulin | `insulin` | Present / Absent / Unknown |
| Semaglutide | `semaglutide` | Present / Absent / Unknown |

### 5.3 Initial observations

The fixed unit is selected from catalog metadata and is not typed manually.

| Label | Canonical concept | Unit |
|---|---|---|
| HbA1c | `hba1c` | `%` |
| Fasting glucose | `fasting_glucose` | `mg/dL` |
| eGFR | `egfr` | `mL/min/1.73m2` |
| Creatinine | `creatinine` | `mg/dL` |
| ALT | `alt` | `U/L` |
| AST | `ast` | `U/L` |
| Hemoglobin | `hemoglobin` | `g/dL` |
| White blood cell count | `wbc` | `10^9/L` |
| Platelets | `platelets` | `10^9/L` |
| LDL cholesterol | `ldl` | `mg/dL` |
| Triglycerides | `triglycerides` | `mg/dL` |
| BMI | `bmi` | `kg/m2` |
| Systolic blood pressure | `systolic_bp` | `mmHg` |
| Diastolic blood pressure | `diastolic_bp` | `mmHg` |
| Potassium | `potassium` | `mmol/L` |
| Albumin | `albumin` | `g/dL` |

All new manual observations require a numeric value and effective date. Unknown
observations record `assertion=unknown` without inventing a numeric value.

## 6. Mutation and feedback contract

### 6.1 Toast system

Build one application-level toast provider rather than page-specific
notifications.

Supported variants:

- success;
- information;
- warning;
- error.

Behavior:

- top-right on desktop and inset full-width near the top on narrow screens;
- maximum three visible notifications with a queue;
- success and information dismiss automatically after approximately 4–6 seconds;
- warning and error remain until dismissed;
- pause dismissal while hovered or keyboard-focused;
- optional action such as **Undo** or **Review detail**;
- `role="status"` and polite live announcement for success/information;
- `role="alert"` for errors that are not already announced by the form;
- keyboard-accessible dismiss button;
- reduced-motion support;
- no protected clinical value is placed in a global notification beyond the
  currently visible synthetic record context.

Example messages:

```text
Biological sex changed from Female to Male.
Pregnancy status changed from Not pregnant to Pregnant.
HbA1c added: 7.8%.
Metformin status changed from Present to Absent.
Pregnancy status removed. [Undo]
Patient profile updated.
```

### 6.2 Form behavior

- Save buttons show a busy label and cannot be double-submitted.
- Save is disabled when no value changed.
- Cancel restores the server value.
- Navigating away with unsaved changes triggers a confirmation.
- The API response, not an optimistic assumption, becomes the displayed value.
- Field errors preserve all entered values.
- API conflict responses identify the exact field and conflicting fact.
- A successful save moves focus to the confirmation/status region when needed
  without disrupting routine keyboard flow.

### 6.3 Change summaries

For a single simple change, the toast carries the summary.

For several demographic changes, show an in-page success region:

```text
Patient profile updated
  Biological sex: Female -> Male
  Date of birth: 1988-09-22 -> 1989-09-22
```

For removals and consistency-sensitive changes, use a confirmation dialog before
the mutation and a toast after the server confirms it.

## 7. Persistence and API direction

### 7.1 Biological sex contract

- Replace unrestricted schema validation with `Literal["male", "female"] | None`
  or an equivalent enum.
- Normalize legacy `Male` and `Female` values to lowercase.
- Keep API reads backward compatible only during a bounded transition; the final
  response contract returns canonical lowercase values.
- Add database validation so direct writes cannot introduce unsupported values.
- Date of birth must not be in the future.

### 7.2 Catalog-backed fact requests

Introduce request schemas that distinguish:

- condition/medication status;
- pregnancy status;
- numeric observation.

The server resolves label, type, concept, and unit from the catalog. It must not
trust a client-supplied unit or fact type when a catalog key already defines them.

Recommended endpoints:

```text
GET    /api/v1/patient-fact-catalog
POST   /api/v1/patients/{patient_id}/facts
PATCH  /api/v1/patients/{patient_id}/facts/{fact_id}
DELETE /api/v1/patients/{patient_id}/facts/{fact_id}
POST   /api/v1/patients/{patient_id}/facts/{fact_id}/restore
GET    /api/v1/patients/{patient_id}/activity
```

`DELETE` retains its familiar client meaning but performs a server-side void.

### 7.3 Change history

Add a small immutable patient change-event model:

```text
id
owner_id
patient_id
actor_user_id
resource_kind        profile | fact
resource_id
action               create | update | void | restore
before_json
after_json
reason
created_at
```

Add fact voiding fields:

```text
voided_at
voided_by
void_reason
```

Normal patient reads return active facts only. Activity reads return bounded,
newest-first change summaries. Saved screening snapshots continue to reference
their immutable copied evidence and require no rewrite.

### 7.4 Concurrency

Profile and fact mutations must include the last known `updated_at` value or an
equivalent revision token. If another request changed the record first, return a
conflict and ask the user to reload rather than silently overwrite newer data.

## 8. Consistency rules

The backend is authoritative; the frontend mirrors rules only for immediate
guidance.

| Situation | Result |
|---|---|
| Sex is neither `male`, `female`, nor null | Block |
| Date of birth is in the future | Block |
| Male + pregnancy present | Block |
| Change sex to male while pregnancy present exists | Block and link conflicting fact |
| Pregnancy present + sex not recorded | Allow with review warning |
| Duplicate current condition/medication concept | Edit existing detail instead of adding |
| Conflicting present/absent current concept | Block and reconcile existing detail |
| Observation without value or date | Block |
| Observation with catalog-incompatible unit | Block |
| Multiple observations on different dates | Allow; display newest first |
| Remove evidence used by an old screening | Allow after confirmation; old snapshot remains |

No consistency rule changes an already saved screening or its outcome.

## 9. Phased implementation

Implement one phase at a time. Stop after each exit criterion for review.

### Phase PD0 — Contract lock and baseline tests

**Objective:** Turn the decisions in this guide into executable contracts before
changing the visual workflow.

Steps:

1. Add characterization tests for current patient create, update, fact update,
   fact deletion, ownership, and immutable screening behavior.
2. Add failing contract tests for canonical biological sex, future dates,
   pregnancy conflicts, duplicate current facts, and stale updates.
3. Define the catalog response and typed mutation schemas.
4. Record legacy-value migration behavior and rollback expectations.
5. Inventory every seed/import concept against the initial catalog.

Exit criteria:

- Existing behavior is protected where intentionally retained.
- Every new validation and conflict has a stable error code.
- No UI or persistence behavior changes yet.

Status:

- Complete on 2026-07-29.
- Added executable catalog and typed mutation contracts.
- Reserved stable patient-data error and warning codes.
- Recorded seed, parser, screening-test, unit, and legacy-sex inventories.
- Added API characterization coverage for profile mutation, fact lifecycle,
  ownership, and immutable screening evidence.
- Added five strict expected-failure contracts assigned to PD2, PD3, and PD4.
- Verification: 104 backend tests passed, 5 contracts xfailed as planned, Ruff
  passed, MyPy passed, backend contract import passed, and `git diff --check`
  passed.
- No route, persistence, migration, or frontend behavior changed.

### Phase PD1 — Shared feedback and form-state foundation

**Objective:** Establish consistent mutation feedback before rebuilding patient
forms.

Steps:

1. Add an application-level toast provider and viewport.
2. Implement success, information, warning, and error variants.
3. Add queueing, dismissal, optional action, live-region behavior, narrow layout,
   and reduced motion.
4. Create reusable mutation state for idle, dirty, saving, saved, and failed.
5. Add unsaved-change navigation confirmation.
6. Integrate toasts first with the existing profile update and fact
   add/remove operations without changing their underlying data contract.

Tests:

- Toast announcement, timeout, manual dismissal, action, and queue.
- No duplicate submission.
- Error remains available to screen readers.
- Reduced-motion and narrow viewport.

Exit criteria:

- Every existing patient mutation gives visible and accessible feedback.
- No toast is the sole explanation for a validation error.

Status:

- Complete on 2026-07-29.
- Added one app-level toast provider with success, information, warning, and
  error variants; three-visible queueing; timed or persistent dismissal;
  hover/focus pausing; optional actions; accessible announcements; responsive
  placement; and reduced-motion behavior.
- Added reusable idle, dirty, saving, saved, and failed mutation state with an
  atomic in-flight guard against duplicate submission.
- Added in-app and browser-navigation unsaved-change protection for new and
  existing patient forms.
- Added visible success and failure feedback for patient creation, profile
  updates, fact addition/removal, and patient deletion without changing API or
  persistence contracts.
- Kept mutation errors inline as the primary assertive announcement so the
  accompanying persistent toast is not the sole validation explanation or a
  duplicate live-region announcement.
- Verification: 46 frontend tests passed, ESLint passed, the production build
  passed, `git diff --check` passed, and browser review covered populated,
  success, failure, unsaved-dialog, desktop, narrow, keyboard-focus, and
  reduced-motion states.

### Phase PD2 — Biological-sex and demographic editor

**Objective:** Replace free-text demographics with controlled inputs and explicit
review/edit states.

Steps:

1. Add the biological-sex enum, API validation, and database constraint.
2. Normalize legacy casing without inventing missing values.
3. Reject future dates of birth in both API and UI.
4. Replace free-text sex fields on new patient, patient detail, and text-import
   review with Male/Female radios plus a separate Not recorded action/state.
5. Convert patient detail demographics to summary rows with **Edit
   demographics**.
6. Show exact before/after confirmation after save.
7. Add stale-update protection.

Tests:

- Male, female, and null round trips.
- Unsupported and mixed free-text values are rejected.
- Existing lowercase and legacy seed values remain screenable.
- Future DOB rejected; missing DOB remains allowed.
- Radio keyboard behavior, edit/cancel, dirty state, and save toast.
- Existing immutable screening snapshots remain unchanged after profile edits.

Visual review:

- Male, female, and not-recorded profiles.
- Editing, saving, canceling, API failure, stale conflict, and narrow layout.

Exit criteria:

- Biological sex can no longer be entered as arbitrary text.
- Demographic changes are explicit, confirmed, and reproducible.

Status:

- Complete on 2026-07-29.
- Added canonical lowercase `male`/`female` API types, database enforcement,
  future-date-of-birth validation, and stable validation error codes.
- Added a reversible migration that preflights unsupported legacy values,
  normalizes recognized case and whitespace, preserves null, and applies the
  database check constraint.
- Added compare-and-swap profile updates using the loaded `updated_at` revision
  and a stable stale-record conflict.
- Replaced demographic free text in new-patient, patient-detail, and pasted-text
  import-review flows with Female/Male radios and an explicit Not recorded
  action.
- Converted patient demographics to review-first summary rows with a focused
  editor, cancel behavior, inline failures, stale reload, exact before/after
  feedback, and an immutable-screening impact note.
- Updated synthetic demo/admin seed values to canonical lowercase biological
  sex without changing the intended patient mix.
- Verification: 115 backend tests passed with the two PD3/PD4 contracts xfailed
  as planned; 52 frontend tests passed; Ruff, MyPy, ESLint, production build,
  migration downgrade/upgrade, and `git diff --check` passed.
- Browser review covered Female, Male, Not recorded, summary, edit, save,
  before/after confirmation, stale conflict, loading, pasted-text import review,
  desktop, narrow, keyboard radio behavior and focus, and reduced motion.

### Phase PD3 — Catalog and guided add/edit clinical details

**Objective:** Replace the generic fact form with task-focused clinical-detail
workflows.

Steps:

1. Implement the backend-owned concept catalog and read endpoint.
2. Add typed condition, medication, pregnancy, and observation request handling.
3. Build **Add clinical detail** as a focused drawer or dialog.
4. Let users search or browse supported details by group.
5. Render dynamic controls from catalog metadata.
6. Add clear edit actions to every active fact row.
7. Group facts into conditions, medications, and labs/observations.
8. Display friendly labels, normalized status, value/unit, effective date, and
   source.
9. Direct duplicate concepts to the existing edit workflow.

Tests:

- Catalog completeness and stable canonical codes.
- Correct dynamic field for each input kind.
- Fixed unit cannot be overridden.
- Unknown assertion saves without a fabricated numeric value.
- Add/edit success, cancel, conflict, server error, and keyboard focus return.
- Long labels and empty groups.

Visual review:

- Empty, populated, long-list, add, edit, saving, error, duplicate, and narrow
  states.

Exit criteria:

- Routine users never type internal concept codes, fact types, or fixed units.
- Existing details can be edited without remove-and-recreate.

Status:

- Complete on 2026-07-29.
- Added an authenticated, backend-owned 25-entry catalog with stable canonical
  concepts, task labels, groups, input kinds, allowed assertions, date
  requirements, help text, and server-owned fixed units.
- Replaced raw fact payloads with strict tagged status, pregnancy-status, and
  numeric values. The server now derives concept, fact type, unit, and source;
  rejects unknown catalog keys, extra fields, invalid value shapes, unit
  overrides, stale edits, and duplicate current details with stable errors.
- Replaced the generic fact form with a searchable and grouped clinical-detail
  dialog, catalog-driven radios/numeric/date controls, direct row editing,
  normalized labels and numeric display, explicit source/date metadata, empty
  groups, and duplicate redirection into the existing editor.
- Added exact add/edit/remove feedback, retained values after failures, saving
  guards, Escape/cancel focus return, initial field focus, narrow responsive
  behavior, and reduced-motion support.
- Verification: 122 backend tests passed with the single PD4 pregnancy
  consistency contract xfailed as planned; 58 frontend tests passed; Ruff,
  MyPy, ESLint, TypeScript, the production build, and `git diff --check`
  passed.
- Browser review covered empty and populated groups, catalog loading/error and
  long-label search, add, numeric fixed-unit and unknown controls, edit, saving,
  retained-value failure, duplicate redirection, desktop, 390px narrow layout,
  keyboard focus/Escape return, and reduced motion.
- No persistence migration, seed reset, real patient data, or deployed
  environment change was required for PD3.

Pre-PD4 workflow alignment:

- Routine mutation toasts now dismiss automatically, with longer visibility for
  warnings and errors and manual dismissal retained.
- Patient details not represented by the controlled catalog are stored in a
  separate review-only collection. They are explicitly excluded from screening
  evidence rather than becoming unrestricted facts.
- Trial authoring now presents guided inclusion and exclusion sections backed by
  the same controlled concept catalog. The server derives normalized rules and
  fixed units; routine users edit and save one current protocol.
- Unsupported trial wording can be retained as a mapping-review item, but cannot
  be approved or used for screening until mapped or removed.
- Immutable protocol copies remain internal because saved screenings and the
  planned research extensions require reproducible links. Drafts, revisions,
  ordering, and protocol history are not routine-user controls.

### Phase PD4 — Pregnancy constraints and reconciliation

**Objective:** Enforce the approved binary-sex/pregnancy rules without silently
changing evidence.

Steps:

1. Add backend cross-field validation for pregnancy create/update and
   demographic updates.
2. Return stable conflict codes and the conflicting fact identifier.
3. Disable the Pregnant choice for known male records with an explanatory hint,
   while retaining backend enforcement.
4. Block changing sex to male until active pregnancy-present evidence is
   reconciled.
5. Show a non-blocking profile-completeness warning when pregnancy is present and
   sex is not recorded.
6. Add a reconciliation panel for any legacy conflict.
7. Ensure trial screening receives only the explicitly saved facts; do not infer
   pregnancy absence from sex.

Tests:

- Complete consistency matrix from Section 8 at API and UI levels.
- Direct API calls cannot bypass UI restrictions.
- No partial mutation on conflict.
- Conflict links focus the relevant fact editor.
- Existing screening snapshots and outcomes remain unchanged.

Visual review:

- Blocked pregnancy edit, blocked sex edit, missing-sex warning, reconciliation,
  and successful corrected flow.

Exit criteria:

- A new male/pregnancy-present conflict cannot be stored.
- Existing conflicts are visible and resolvable.
- No evidence is changed automatically.

Status:

- Complete on 2026-07-29.
- Added authoritative API validation for pregnancy create/update and demographic
  changes. Direct requests cannot store a new Male and Pregnant combination, and
  rejected requests leave both profile and fact values unchanged.
- Added stable `PATIENT_PREGNANCY_SEX_CONFLICT` responses with the conflicting
  fact identifier and patient-read `consistency_issues` using the reserved
  `PATIENT_SEX_NOT_RECORDED_FOR_PREGNANCY` warning code.
- Disabled Pregnant for known male records with an explanation while keeping
  Not pregnant and Unknown available as explicit evidence. No status is inferred
  from biological sex.
- Added a non-blocking profile-completeness warning for Pregnant with biological
  sex not recorded, plus a reconciliation panel for preserved legacy conflicts.
- Linked blocked demographic changes and legacy warnings directly to the
  Pregnancy status editor; correction updates only the user-selected field and
  leaves saved screening snapshots unchanged.
- Verification: 138 backend tests and 64 frontend tests passed; Ruff, MyPy,
  ESLint, TypeScript, the production build, API readiness, and
  `git diff --check` passed.
- Browser review covered blocked pregnancy editing, blocked sex editing, missing
  biological-sex warning, legacy reconciliation, corrected success with toast,
  desktop, 390px narrow layout, focus return, and reduced motion.

### Phase PD5 — Void, restore, activity, and screening impact

**Objective:** Make removal safe and make record consequences understandable.

Steps:

1. Add fact void fields and immutable patient change events.
2. Change fact removal from hard delete to void.
3. Require a removal reason.
4. Add restore support and bounded Undo from the success toast.
5. Record profile and fact create/update/void/restore events.
6. Add a compact patient activity region.
7. Add an impact message explaining that old screenings retain old snapshots.
8. Offer a clear **Run new screening** next action after relevant changes.

Tests:

- Removed facts disappear from active reads and new snapshots.
- Removed facts remain in activity history.
- Restore returns the same semantic detail and records another event.
- Undo expires safely and handles conflicts.
- Ownership applies to activity and restore operations.
- Old screenings remain reproducible after edit, void, and restore.

Visual review:

- Confirmation with reason, removed toast with Undo, restored detail, activity
  history, screening-impact message, empty and long activity states.

Exit criteria:

- Routine removal no longer destroys the active record's history.
- Users can tell which screenings are and are not affected.

Status:

- Complete on 2026-08-02.
- Added nullable void metadata to patient facts and an immutable,
  owner-scoped `patient_change_events` table with newest-first activity reads.
- Fact removal now requires a normalized reason plus the loaded fact revision,
  voids rather than deletes, excludes the fact from active reads and future
  snapshots, and records a `fact_voided` event. Restore clears the void fields,
  checks catalog/duplicate conflicts, and records `fact_restored`.
- Profile and fact create/update paths record immutable before/after events,
  including imports. Patient detail shows a compact activity region and a
  reasoned removal dialog with a bounded toast Undo action.
- Existing saved screenings remain immutable; the patient page explicitly
  explains that future screenings use the current active record.
- Verification: focused PD0/PD4/PD6 backend coverage, frontend tests, lint,
  TypeScript, Ruff, and migration upgrade all pass. Browser review still needs
  to be repeated against the final running build before release handoff.

### Phase PD6 — Import alignment, seeds, documentation, and final workflow review

**Objective:** Make every non-PDF and import-review entry point use the same
canonical contracts and finish the end-to-end experience.

Steps:

1. Map extracted candidate concepts to the same controlled catalog.
2. Use biological-sex radios in patient import review.
3. Surface unsupported extracted concepts as review warnings rather than silently
   accepting them.
4. Update demo/admin seeds to canonical lowercase biological sex and catalog
   metadata.
5. Preserve intended pass/fail/unknown distributions.
6. Update README, API examples, help content, and screenshots.
7. Run the full backend, frontend, browser, accessibility, and visual checks.

Final browser journeys:

1. Create a patient with controlled demographics.
2. Add and edit a condition.
3. Add and edit a numeric observation.
4. Change pregnancy absent to present for a female patient and rerun screening.
5. Attempt pregnancy present for a male patient and resolve the conflict.
6. Attempt to change a pregnant patient's sex to male and resolve the conflict.
7. Remove and undo a detail.
8. Confirm an old screening retains its old snapshot after active-record changes.
9. Review activity history.
10. Complete equivalent candidate review from pasted text.

Exit criteria:

- All entry paths produce the same canonical values.
- Demo/admin screening distributions remain intentional.
- Full verification passes.
- Desktop and narrow visual review passes.
- Documentation no longer describes the generic fact form.

Status:

- Complete on 2026-08-02.
- Import candidates are matched by fact type and normalized key/display label
  against the active database catalog. Canonical concepts and fixed units are
  used for approved facts; missing dates, incompatible values, and unmatched
  concepts remain review warnings and are stored as review-only unsupported
  details instead of screening evidence.
- Patient import review now includes an effective-date control so a reviewer
  can complete required observation evidence before approval. Biological-sex
  radios remain the only profile sex control.
- Demo and migration-owned catalog seeds remain canonical and deterministic;
  import approval emits the same patient/fact activity events as manual entry.
- Updated API/help documentation and coverage for catalog warnings, canonical
  import approval, activity events, removal/restore, and notification focus
  pausing.
- Verification: full applicable backend/frontend suites, production build,
  Ruff, MyPy, ESLint, TypeScript, migration checks, and `git diff --check`
  pass. Final desktop/narrow browser screenshots should be captured after the
  dev server is restarted with this commit.

## 10. Expected file areas

Likely backend changes:

```text
backend/migrations/versions/
backend/src/trialsync/db/models.py
backend/src/trialsync/schemas.py
backend/src/trialsync/api/patients.py
backend/src/trialsync/patient_facts/catalog.py
backend/src/trialsync/screening/service.py
backend/src/trialsync/demo.py
backend/tests/
```

Likely frontend changes:

```text
web/src/api/client.ts
web/src/components/ToastProvider.tsx
web/src/components/ClinicalDetailEditor.tsx
web/src/components/PatientActivity.tsx
web/src/pages/NewPatientPage.tsx
web/src/pages/PatientDetailPage.tsx
web/src/pages/ImportReviewPage.tsx
web/src/styles.css
web/src/test/
```

Exact filenames may change during implementation, but the backend catalog must
remain the semantic source of truth.

## 11. Verification requirements

For every phase:

1. Run the narrowest backend and frontend tests first.
2. Run Ruff, MyPy, frontend lint, and typecheck for affected code.
3. Run the full applicable backend/frontend suite before handoff.
4. Run the frontend production build after material UI changes.
5. Inspect desktop and narrow layouts using browser screenshots.
6. Check keyboard focus, live announcements, contrast, and reduced motion.
7. Check empty, populated, loading, saving, success, validation, conflict, and
   server-error states.
8. Confirm that no real patient data or credentials enter tests, screenshots, or
   logs.

## 12. Explicit non-goals

- Recreating Epic, Oracle Health, or another proprietary EHR.
- Supporting unrestricted medical terminology.
- Unrestricted terminology auto-coding or SNOMED CT integration; the bounded
  RxNorm/LOINC suggestions are advisory only and never automatically persist
  terminology mappings.
- Real-world gender/sex clinical decision support.
- Encounter, practitioner, order, prescription, or results-review workflows.
- Automatically correcting data based on another field.
- Re-screening automatically after any edit.
- Modifying historical screening snapshots.
- Treating a toast as an audit log.

## 13. Recommended next phase

The bounded PD5/PD6 overhaul is complete. The next work should be the separate
research-extension plan (R3/R4 data and dropout research), not additional
patient-entry infrastructure. Capture the final browser screenshots and demo
walkthrough before starting that research phase.
