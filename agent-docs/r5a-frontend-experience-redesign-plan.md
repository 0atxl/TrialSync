# TrialSync R5A Frontend Experience Redesign

**Date:** 2026-08-25
**Status:** R5A-0 through R5A-3 and the shared-CSS audit are accepted. R5A-4 is implemented and awaiting visual review.
**Relationship to the research plan:** R5A is the frontend experience gate after the implemented
R5/R6 research integration and before R7. It redesigns the full application experience without
changing deterministic eligibility, the accepted `xgboost-05` runtime model, or the sealed R6 V3
cohort representations and indexes.

## 1. Purpose

Rebuild TrialSync's frontend around user tasks instead of backend architecture. The current
application exposes too much provenance, repeats explanatory copy, uses inconsistent ingestion
patterns, and presents research capabilities as technical reports rather than useful interactive
workflows.

R5A is a product-wide experience redesign, not a CSS reskin. It covers login, navigation, the
overview dashboard, patient and trial ingestion, record lists and details, screening, dropout
follow-up and population review, Cohort Atlas exploration, catalog access, Help, and all shared
loading/error/empty states.

The finished application should feel like a polished BTech project demonstration:

- compact and understandable without training;
- visually distinctive without decorative excess;
- consistent across manual entry, document import, editing, and review;
- interactive where visualization materially improves understanding;
- technically reproducible without placing backend terminology in the default workflow.

## 2. Fixed decisions

These decisions were approved by the user on 2026-08-25.

### 2.1 Product posture

- TrialSync remains a BTech academic project, not a startup product or hospital deployment.
- Normal pages do not repeat environment, alpha, synthetic-demo, deployment, or operational-use
  statements.
- Research outputs use one concise boundary near the result: they do not change the deterministic
  screening result. Comprehensive methodology and limitations belong in Help and optional
  technical details.
- The existing teal/neutral color direction remains, with improved typography, spacing,
  interaction states, iconography, and chart styling.
- The interface must not look like a generic AI dashboard or a collection of generated cards.

### 2.2 Information hierarchy

- Show information by default only when it helps the user find, enter, review, compare, or act.
- Internal UUIDs, hashes, checksums, run IDs, vector dimensions, artifact locators, schema names,
  and immutable-version identifiers are hidden from normal views.
- Model and algorithm names are hidden from primary research results.
- Reproducibility metadata remains available through a consistent **Technical details** disclosure
  and Help documentation.
- Trial versioning remains authoritative in the backend but appears to ordinary users as one
  current saved protocol with a simple updated date/status where useful.
- Each page has one title, at most one short orientation sentence when required, and one primary
  action. Do not add a punchline or eyebrow label to every region.

### 2.3 Navigation

Primary navigation is:

1. Overview
2. Patients
3. Trials
4. Screenings
5. Research
6. Help

Additional rules:

- Batch screening moves inside Screenings and is not a primary navigation item.
- Patient and trial import start from their respective **Add** flows.
- Research contains **Dropout** and **Cohorts**, with Dropout as the default research route.
- Catalog management is removed from primary navigation. It remains available to authorized
  catalog administrators through a small administration area.
- Route compatibility should be preserved with redirects where an existing bookmark changes.

### 2.4 Ingestion

- Patient and trial creation use full-page, step-based flows.
- **Manual entry** and **Import document** are the two starting choices in the same flow.
- Imported candidates converge into the same canonical review form used by manual entry.
- Complex creation and review do not occur in a modal. Modals are reserved for confirmation or a
  bounded quick action; drawers may support a focused add/edit action without replacing the page.
- Concept search and terminology suggestions appear inline while entering clinical details or
  criteria. Ordinary users do not visit a catalog page first.
- Different controls are expected when they match the data. Consistency means a shared field
  anatomy, validation behavior, action placement, and progression—not forcing every value into the
  same control type.

### 2.5 Research

- A saved screening retains compact, independent actions for dropout, cohort context, and similar
  participants.
- Research also has a separate Dropout dashboard covering potentially eligible screenings and
  their follow-up/prediction states.
- The Cohort Atlas becomes an interactive, zoomable node visualization with visible clusters,
  search, filtering, hover/focus, selection, and exact-neighbor highlighting.
- Reference members use stable generated display names. Raw member IDs never act as visible names.
- Desktop and narrow laptop/tablet widths are the supported R5A targets.

### 2.6 Delivery

- Complete one UX preflight, then implement R5A in seven reviewable stages and stop for review
  after each stage.
- Small additive backend changes are allowed when they materially improve the approved UX.
- Backend work must be identified before implementation, remain backward compatible where
  practical, and must not rewire deterministic screening or retrain/rebuild accepted research
  models casually.

## 3. Preserved contracts

R5A must preserve:

- one immutable patient snapshot evaluated against one approved trial version;
- deterministic `pass`, `fail`, and `unknown` criterion evaluation;
- unchanged saved screening outcomes and evidence;
- bounded batch screening as a wrapper around exact single-screening logic;
- backend-owned patient fact catalog and canonical units;
- patient change history, void/restore behavior, and stale-update protection;
- review-before-approval import behavior;
- explicit missing information; missing never becomes an observed zero;
- immutable screening-to-research-enrollment linkage;
- the packaged `xgboost-05` day-30-to-day-90 runtime without retraining;
- separate probability, threshold, and explanation provenance;
- the configured active R6 run from environment settings;
- frozen R6 transformations, DBSCAN analysis, PCA coordinates, and exact cosine indexes;
- saved screenings as out-of-sample R6 queries that do not mutate the reference cohort;
- authentication, ownership, report generation, and explanation-chat boundaries.

The completed patient-data plan remains the semantic contract. R5A may replace its dialog/drawer
presentation and surrounding page hierarchy, but not reopen its validated catalog, mutation,
pregnancy-consistency, activity, or immutable-screening rules.

## 4. Experience principles

### 4.1 Task before explanation

- Start with the record, result, or action.
- Keep guidance adjacent to the field or decision it supports.
- Move tutorials, methodology, provenance definitions, and comprehensive caveats to Help.
- Prefer concise labels, icons with accessible names, and progressive disclosure over paragraphs.

### 4.2 Progressive disclosure

- Show one step or decision region at a time during ingestion.
- Show summary mode before edit mode on record details.
- Show research status and next action before forms or technical results.
- Put full evidence, activity, and technical provenance behind intentional expansion when they are
  not the current task.

### 4.3 Consistent interaction grammar

- Full page: creation, import/review, screening setup, and multi-step research follow-up.
- Side panel/drawer: bounded detail inspection or quick add/edit while retaining list/graph context.
- Modal: confirmation, destructive action, or one small choice.
- Inline expansion: evidence rows, activity details, neighbor differences, and technical details.
- Toast: concise mutation outcome; never the only validation explanation.

### 4.4 Visual restraint

- Avoid nested cards, excessive pills, repeated bordered boxes, decorative metrics, and large empty
  hero regions.
- Use tables, grouped rows, split panes, charts, and full-canvas visualizations where appropriate.
- Use semantic pass/fail/unknown colors only for eligibility evidence.
- Dropout bands and cohort groups use a separate restrained analytical palette.
- Use one icon library consistently; icons supplement rather than replace accessible labels.

## 5. Target information architecture

```text
Login / Register

Application shell
  Overview
  Patients
    Patient list
    Add patient: manual | document import -> common review -> save
    Patient detail: summary | clinical details | activity | screenings
  Trials
    Trial list
    Add trial: manual | document import -> common criteria review -> save
    Trial detail: summary | criteria | screenings
  Screenings
    History
    New screening
    Batch screening
    Screening detail: result | evidence | research | report/help
  Research
    Dropout dashboard
    Cohort Atlas
  Help
  Administration (authorized users only)
    Concept catalog
```

## 6. Shared visual and component foundation

### 6.1 Design tokens

Consolidate and document tokens for:

- brand, surface, text, border, focus, and analytical colors;
- 4/8px spacing rhythm;
- typography scale and tabular-number treatment;
- radius, shadow, motion duration, and easing;
- desktop and narrow-laptop/tablet breakpoints;
- chart and graph palettes with sufficient contrast.

Remove accumulated one-off colors, radii, and duplicate component declarations where possible.

### 6.2 Shared components

Create or consolidate:

- icon button and labelled action button;
- compact page header;
- search/filter toolbar;
- data table and responsive record list;
- status summary and eligibility state treatment;
- empty, loading, error, and permission states;
- field wrapper with label, hint, validation, unit, and required state;
- searchable catalog/terminology combobox;
- segmented source choice for Manual entry / Import document;
- step header and completion summary;
- side panel/drawer and confirmation dialog;
- chart tooltip and accessible text alternative;
- technical-details disclosure;
- graph toolbar, legend, tooltip, and selection panel.

Use `lucide-react` or one equivalent restrained icon package after dependency review. Do not mix
icon systems or use letter glyphs as the final navigation icons.

### 6.3 Content rules

Default UI copy must not expose these terms unless the user opens technical details or Help:

- UUID, checksum, hash, artifact, schema version;
- XGBoost candidate ID, SHAP, DBSCAN, FAISS, `IndexFlatIP`, PCA, vector dimension;
- frozen representation, core radius, out-of-sample, feature contract;
- approved trial version ID or immutable linkage.

Plain-language replacements include:

- **Dropout estimate** instead of model-risk workspace;
- **Factors affecting this estimate** instead of SHAP contributions;
- **Cohort group** or **Outside a dense group** instead of DBSCAN labels/noise jargon;
- **Similar patients** instead of exact external-vector query;
- **Clinical details** instead of facts/features;
- **Current trial criteria** instead of approved immutable trial version.

Do not add vague claims such as “AI-powered insights.”

## 7. Route requirements

### 7.1 Login and registration

- Compact authentication panel with TrialSync identity, fields, and primary action.
- Preserve login/register behavior and accessible error handling.
- Remove feature manifestos, environment/version badges, and excessive project explanation.
- Use the retained color direction through typography and one subtle background/brand treatment.
- Verify autofill, password visibility, keyboard submission, failure, and narrow states.

### 7.2 Application shell

- Replace navigation letter glyphs with consistent icons.
- Keep primary labels visible in normal desktop mode; retain a usable collapsed mode.
- Remove the generic brand subtitle if it adds no navigation value.
- Place account and sign-out controls predictably without dominating the top bar.
- Remove cross-page action duplication.

### 7.3 Overview

The Overview answers “What is happening?” with a small number of linked visual summaries:

1. eligibility distribution;
2. screening activity over time;
3. dropout workflow status for potentially eligible screenings;
4. records requiring attention;
5. recent screenings.

Requirements:

- Chart segments filter or navigate to the corresponding records.
- Avoid a grid of unrelated metric cards.
- Every visualization has a text/table alternative and meaningful empty state.
- Do not add analytics unsupported by stored data.
- Keep the recent list compact; do not repeat actions already available in navigation.

### 7.4 Patients and patient detail

Patient list:

- search, useful filters, patient list, and one **Add patient** action;
- display human identity and concise screening-relevant summary;
- no internal IDs, hashes, or unrelated screening buttons;
- responsive table/list behavior without horizontal overflow.

Patient detail:

- concise identity header and edit action;
- demographics summary;
- grouped conditions, medications, and observations;
- inline search/filter for long clinical-detail lists;
- recent activity and patient screening history as secondary sections;
- existing immutable-screening impact explanation moves to Help or a compact contextual notice
  shown only after a relevant mutation.

### 7.5 Patient ingestion

```text
Add patient
  -> choose Manual entry or Import document
  -> Basics
  -> Clinical details
  -> Review
  -> Save
```

Manual entry:

- collect name, date of birth, and biological sex first;
- search/add supported clinical concepts inline;
- render catalog-driven status, numeric, date, and fixed-unit controls;
- allow review-only unsupported details without treating them as screening evidence;
- preserve unsaved-change protection and server-authoritative validation.

Document import:

- one upload/drop region supporting existing text/PDF rules;
- visible but concise extraction progress;
- populate the same Basics and Clinical details steps;
- visually distinguish confirmed, uncertain, missing, and unsupported candidates;
- require review before save;
- do not expose OCR/provider implementation unless an actionable error requires it.

### 7.6 Trials and trial detail

Trial list:

- search, useful status filter, trial list, and one **Add trial** action;
- display title, registry reference, concise criteria count, and updated date;
- hide routine version-management language and IDs.

Trial detail:

- summary and editable current protocol;
- structured inclusion and exclusion criteria;
- clear unsupported/mapping-review state;
- related screenings as a secondary view;
- technical history available only in Technical details or administration/help.

### 7.7 Trial ingestion

```text
Add trial
  -> choose Manual entry or Import document
  -> Trial basics
  -> Inclusion criteria
  -> Exclusion criteria
  -> Review
  -> Save current protocol
```

- Both sources use the same criteria review UI.
- Inline controlled-concept and terminology suggestions are available during criterion authoring.
- Criteria rows use plain labels and operators; normalized DSL/rule JSON remains hidden.
- Long source wording remains inspectable without dominating the editor.
- Approval remains explicit and review-first.

### 7.8 Screenings

Screening history:

- patient/trial search, result/date filters, history table, and **New screening**;
- Batch screening is a secondary action within this page;
- no duplicate creation actions elsewhere unless they are a direct contextual next step.

New screening:

- concise patient and trial selection;
- searchable selectors when lists are long;
- show only enough context to avoid selecting the wrong records;
- result navigates directly to the saved screening detail.

Screening detail priority:

1. patient and trial names;
2. deterministic eligibility result;
3. criteria grouped by failed, missing/review, and passed evidence;
4. report and explanation actions;
5. compact research actions.

Engine versions, DSL versions, hashes, source snapshot IDs, and similar fields move to Technical
details. The explanation chat remains available but must not dominate criterion evidence.

### 7.9 Individual dropout workflow

Use a three-stage status flow:

```text
Baseline setup -> Day-30 follow-up -> Dropout estimate
```

- Show the current stage and one next action.
- Baseline values from the screening are summarized, not displayed as a technical feature ledger.
- Enrollment-only values are grouped into a concise form with consistent field anatomy.
- Day-30 dose, visit, measurement, and adverse-event capture uses focused add actions plus a
  readable event summary, not four permanently expanded forms.
- Empty event categories require explicit reviewed-none confirmation where zero has meaning.
- Snapshot construction is described as **Review day-30 information**, not as feature engineering.
- Missing information is listed in human terms and never silently converted to zero.
- The result shows probability, a readable threshold marker, horizon, and human-labelled factors.
- Model name/version and numeric contribution values live in Technical details.
- One concise boundary states that the estimate does not change eligibility.

### 7.10 Dropout dashboard

Research opens on a Dropout dashboard that includes all potentially eligible saved screenings,
whether or not follow-up or prediction exists.

Primary table:

| Patient | Trial | Follow-up status | Dropout estimate | Updated | Action |
|---|---|---|---|---|---|

Supporting visualization:

- not started;
- information needed;
- ready to predict;
- prediction available;
- estimate distribution for predicted records only.

Requirements:

- Filters and chart selections update the table.
- Missing prediction is shown as a workflow state, not `0%`.
- Trial-level eligibility and prediction denominators remain correct but are expressed in plain
  language.
- Selecting a row opens the relevant saved screening and dropout stage.
- No model candidate names appear in the default dashboard.

### 7.11 Cohort Atlas

The Atlas uses the Quartz graph-view interaction pattern as inspiration—pan, zoom, drag/focus,
hover labels, and local selection—while preserving TrialSync's actual analytical semantics.

Layout:

```text
Top toolbar: search | perspective | filters | reset/fit
Main canvas: patient nodes, cluster regions, selected-neighbor links
Side panel: selected patient, group context, similarities, differences
Compact legend and one methodology/help action
```

Graph rules:

- Render one node per reference member and an optional saved-screening overlay.
- Use existing seeded PCA coordinates as the initial display position.
- Do not replace analytical positions with an arbitrary force layout or imply that visual distance
  alone is exact similarity.
- Draw soft cluster hulls/regions so clusters look like groups rather than isolated elliptical
  ornaments.
- Render noise/unassigned nodes neutrally outside group emphasis.
- Hide labels until hover, keyboard focus, search match, or selection.
- Support pan, zoom, fit, reset, hover/focus, click/select, and keyboard-accessible member selection.
- Show edges only from the selected patient to exact nearest neighbors.
- Use full-space exact cosine values for neighbor ranking; do not infer neighbors from 2D distance.
- Keep 750 nodes responsive. Prefer SVG with measured performance; move node rendering to Canvas
  only if profiling demonstrates a need and preserve an accessible structured member list.

Selected-patient panel:

- stable generated display name;
- age band and relevant recorded conditions;
- cohort group or **Outside a dense group**;
- plain-language shared characteristics and meaningful contrasts;
- nearest patients with concise similarity values;
- link to the saved screening when the selected node is an external overlay;
- no UUID, run ID, index type, vector dimension, raw feature key, or algorithm label.

Methodology remains available in Help and Technical details. The default view says only that the
map is an approximate visual arrangement and similarity uses the complete recorded profile.

### 7.12 Help and administration

Help becomes the authoritative home for:

- manual entry and document-import guidance;
- screening pass/fail/unknown behavior;
- trial protocol history/versioning;
- dropout observation window, horizon, model, threshold, and factor explanation;
- cohort perspective, grouping, map approximation, similarity, and limitations;
- technical provenance and academic-project scope.

Catalog administration remains available only to authorized users through a compact administration
entry. It manages the backend-owned supported concept set and terminology mappings; ordinary users
receive the same catalog through inline search.

## 8. Backend and data work allowed in R5A

R5A is frontend-led, but the following additive backend work is anticipated.

### 8.1 Overview aggregate

Add one owner-scoped dashboard summary endpoint if existing list endpoints cannot provide the
approved charts without N+1 requests or excessive payloads. It may return:

- eligibility counts;
- bounded screening activity by date;
- potentially eligible dropout workflow counts;
- attention items and recent screening summaries.

Do not persist duplicate dashboard state.

### 8.2 Dropout worklist

Extend or add an owner-scoped dropout-overview endpoint returning one row per potentially eligible
screening with patient/trial labels, follow-up state, latest prediction summary, and next action.
Continue resolving predictions through immutable research enrollment linkage. Never infer a missing
prediction as zero or mix incompatible model/horizon/band versions.

### 8.3 Stable cohort display names

Expose a stable fictional display name for each reference member and saved-screening overlay.

- Prefer an existing generated patient display name when one is already part of sealed source
  metadata.
- Otherwise add a versioned deterministic display-name sidecar keyed by member ID.
- Do not change vectors, cluster labels, PCA coordinates, index order, or the configured active run.
- Do not overwrite the active R6 run casually or regenerate the model/cohort merely for labels.

### 8.4 Cohort explanation summaries

Add human-readable, non-causal summaries only if the existing member and difference payloads are
insufficient. Candidate additions:

- top group characteristics from post-analysis aggregate composition;
- selected member's shared characteristics with its group/neighbors;
- readable criterion labels for screening-profile differences;
- saved-screening display label and detail link.

These are display summaries derived from existing frozen data. They do not become features,
screening evidence, cluster-selection inputs, or recommendations.

### 8.5 Route and response compatibility

- Prefer additive response fields and new aggregate routes.
- Record every genuine contract change in the relevant API/data map documentation.
- Add migrations only for durable state that cannot be derived safely.
- Preserve research-degraded behavior: core screening must still load if a research artifact is
  unavailable.

Before implementing any backend item, document why existing contracts are insufficient and the
smallest accepted change.

## 9. Implementation stages

Complete the R5A-0 preflight first, then implement one stage at a time. Each stage ends with tests,
desktop/narrow visual review, a concise handoff, and user approval before continuing.

### R5A-0 — UX inventory and regression contract

Objective: establish the exact content and behavior baseline before replacing components.

Preflight evidence is recorded in
[`r5a-ux-inventory-and-regression-contract.md`](r5a-ux-inventory-and-regression-contract.md).
The user accepted it on 2026-08-25 and authorized R5A-1.

Steps:

1. Inventory every route, action, form, dialog/drawer, user-visible technical field, repeated
   paragraph, and responsive state.
2. Map existing APIs and tests to the target routes in this plan.
3. Identify existing components/contracts to preserve, consolidate, replace, or retire.
4. Record the exact backend gaps from Section 8; do not implement speculative APIs.
5. Add route-level characterization tests for critical current behavior where coverage is missing.
6. Produce low-fidelity page structures for Overview, ingestion, screening detail, Dropout, and
   Cohort Atlas before code changes.

Exit criteria:

- Every existing feature has an explicit destination, replacement, or retirement reason.
- No deterministic, import-review, mutation, report, chat, R5, or R6 behavior can disappear
  accidentally during redesign.
- Backend additions are bounded and listed.

### R5A-1 — Design foundation, login, shell, and navigation

Objective: establish the visual and interaction system used by every later stage.

Implementation status on 2026-08-25: the shared tokens/primitives, compact authentication pages,
six-destination icon navigation, account administration menu, desktop collapse behavior, shared
error treatment, and Research/Catalog redirects are implemented. Unit, lint, type, and
production-build checks passed. The user accepted the stage on 2026-08-25 and authorized R5A-2.

Steps:

1. Consolidate tokens and base typography/layout.
2. Add the selected icon package and shared icon/action primitives.
3. Build shared page header, toolbar, state, drawer/dialog, technical-details, and form components.
4. Redesign login/register.
5. Redesign the application shell and approved navigation.
6. Move Batch, Research subroutes, Catalog administration, and redirects into the target hierarchy.
7. Remove global redundant copy and action duplication.

Exit criteria:

- Login and shell establish the approved visual direction.
- Navigation contains only the six approved primary items.
- Existing routes remain reachable or redirect intentionally.
- Keyboard, reduced-motion, desktop, and narrow laptop/tablet shell states pass.

### R5A-2 — Visual Overview dashboard

Objective: replace the screening-stat landing page with an actionable at-a-glance dashboard.

Implementation status on 2026-08-25: the bounded owner-scoped Overview aggregate, eligibility and
eight-week activity charts, dropout workflow summary, attention and recent-screening lists, linked
record filters, and loading/empty/error/research-degraded/responsive states are implemented. The
user accepted the stage and the bounded shared-CSS audit before authorizing R5A-3.

Steps:

1. Implement the bounded overview aggregate if required.
2. Add eligibility distribution and activity visualizations.
3. Add dropout workflow visualization.
4. Add attention and recent-screening sections.
5. Connect chart/filter interactions to records.
6. Implement empty, loading, partial/degraded, error, long-label, and narrow states.

Exit criteria:

- Every chart answers a defined question and links to underlying records.
- Missing research capability does not break core dashboard content.
- The dashboard is not a grid of decorative metric cards.

### R5A-2.1 — Shared CSS audit

The user authorized a bounded shared-style audit before R5A-3 after stale page, Help, and navigation
rules caused visible cascade conflicts. The completed audit is recorded in
[`r5a-shared-css-audit.md`](r5a-shared-css-audit.md). It consolidates shared shell, page,
authentication, and action ownership while deliberately deferring feature-specific cleanup to the
stage that redesigns each feature.

### R5A-3 — Unified patient/trial ingestion

Objective: make manual entry and document import two smooth paths through one consistent review
experience.

Implementation status on 2026-08-25: Patients and Trials now expose one Add action with manual and
document source choices. Manual and imported records use the same full-page step anatomy and final
review surfaces. Patient details and trial criteria use the active catalog inline; authenticated
users can request advisory medication/observation terminology suggestions without gaining catalog
administration rights. Unsupported suggestions and extracted candidates remain explicit review
items. Legacy import-entry URLs redirect into the appropriate Add flow. The pre-acceptance cleanup
split the global stylesheet and import-review implementation into owned modules, removed generic
page punchlines, and hid record/version identifiers from the redesigned list and selection flows.
Automated checks pass; the stage is awaiting desktop and narrow-laptop/tablet visual review.

Steps:

1. Build the shared source-choice and step-flow foundation.
2. Rebuild Add patient and patient import review around one canonical form.
3. Integrate catalog and RxNorm/LOINC suggestions inline.
4. Rebuild Add trial and trial import review around one criteria editor.
5. Keep unsupported candidates visible as review items rather than silently accepting them.
6. Preserve dirty-state, validation, conflict, provider-failure, OCR, and approval behavior.

Exit criteria:

- Manual and imported records converge into the same canonical review surfaces.
- Ordinary users never navigate to Catalog before entering data.
- Controls match their data while sharing consistent anatomy and actions.
- PDF/text parsing never strands the user in a disconnected workflow.

### R5A-4 — Core record and screening pages

Objective: simplify Patients, Trials, Screenings, and their details around finding and reviewing
records.

Implementation note (2026-08-25): the patient and trial detail pages now lead with names and
current record content, move record/version metadata into Technical details, and place recent
screenings and activity secondarily. Screening history has direct result and date filters. Saved
screening details lead with patient/trial identity and deterministic eligibility, group complete
criterion evidence into not-met, review, and satisfied sections, keep report/explanation actions
secondary, and retain compact independent research actions. A follow-up replaces existing-record
detail/criterion modals with inline editors, keeps suggestion dropdowns from resizing ingestion
cards, and merges condition, medication, and observation suggestions during ordinary typing. The
external-only selection path now uses one compact setup dialog: routine users retain the existing
review-only path, while catalog administrators can confirm category/unit, add the term through the
existing catalog API, and continue in the inline value or criterion editor. The only additive
backend changes are owner-scoped screening-history filters and the broadened existing terminology
suggestion response; deterministic screening contracts remain unchanged.

Steps:

1. Redesign patient/trial lists and details.
2. Redesign screening history, single screening, and batch entry placement.
3. Redesign screening detail hierarchy without changing evidence/result semantics.
4. Integrate report and explanation actions without dominating the result.
5. Remove raw IDs/version metadata from default pages and add Technical details where justified.
6. Reconcile activity/history placement and eliminate redundant calls to action.

Exit criteria:

- Each list supports search, relevant filters, one primary action, and compact responsive rows.
- Each detail page leads with the record and actions relevant to it.
- Screening evidence remains complete and deterministic eligibility remains visually dominant.

### R5A-5 — Dropout workflow and dashboard

Objective: turn R5 into a clear patient-level process plus a useful population worklist.

Steps:

1. Implement the dropout worklist contract if required.
2. Build Research > Dropout dashboard and filters.
3. Replace the current all-at-once follow-up panel with the three-stage workflow.
4. Build focused event add/review interactions and explicit reviewed-none handling.
5. Present prediction probability, threshold, horizon, and human-readable factors.
6. Move model/provenance values into Technical details and Help.
7. Verify that eligibility is unchanged before and after every research mutation.

Exit criteria:

- Potentially eligible screenings are visible whether unlinked, incomplete, ready, or predicted.
- The next action is obvious for every row and every individual screening.
- Missing follow-up data is never displayed or submitted as observed zero.
- No model/feature jargon is necessary to use the workflow.

### R5A-6 — Interactive Cohort Atlas

Objective: turn R6 into a discoverable graph experience with meaningful patient context.

Steps:

1. Add stable display labels and bounded explanation summaries if required.
2. Build the graph canvas, cluster regions, analytical palette, toolbar, and responsive shell.
3. Add pan, zoom, fit/reset, hover/focus, search, filters, and perspective switching.
4. Add saved-screening overlay and exact selected-neighbor links.
5. Build the selected-patient panel with shared characteristics and differences.
6. Preserve a structured list/table alternative for accessibility and narrow laptop/tablet use.
7. Profile 750-node interaction and remove animation that harms clarity or performance.

Exit criteria:

- Clusters read visually as groups.
- A selected patient is identifiable by a human label and useful attributes.
- The UI explains similarities/differences without raw feature jargon.
- Exact neighbor ranking remains full-space cosine; the 2D map remains display-only.
- No cohort output becomes eligibility evidence or a recommendation.

### R5A-7 — Content cleanup, Help, and final acceptance

Objective: remove residual clutter and prove the complete redesigned workflow.

Steps:

1. Search all user-visible copy for redundant slogans, technical identifiers, repeated
   disclaimers, and obsolete route language.
2. Rewrite Help to hold the moved workflow, methodology, provenance, and limitation content.
3. Complete catalog-administration placement.
4. Remove retired components/styles/routes after dependency and test review.
5. Run full frontend/backend, migration, accessibility, performance, and visual checks.
6. Capture final desktop and narrow-laptop/tablet evidence for each primary journey.
7. Update architecture, API, flow, and handoff documentation only where behavior changed.

Exit criteria:

- Every primary route passes populated, empty, loading, error, long-content, keyboard, reduced-
  motion, and responsive review.
- No ordinary page exposes backend identifiers without an intentional Technical details action.
- No comprehensive methodology is duplicated outside Help.
- Existing core and research tests pass.
- The user accepts R5A before R7 begins.

## 10. Testing and visual QA

### 10.1 Automated checks

For every stage, run the narrowest affected tests first, then:

- frontend unit/component tests;
- ESLint;
- TypeScript typecheck;
- frontend production build;
- relevant backend tests for changed APIs/services;
- Ruff and MyPy for changed backend code;
- migration upgrade/downgrade checks when persistence changes;
- `git diff --check`.

Add browser workflow coverage for:

- authentication;
- patient and trial manual entry;
- patient and trial document import/review;
- patient/trial search and editing;
- single and batch screening;
- screening evidence, report, and explanation;
- dropout unlinked, incomplete, ready, and predicted states;
- dropout dashboard filtering;
- cohort search, filters, graph navigation, selection, neighbor inspection, and saved-screening
  overlay.

### 10.2 Required visual states

Inspect at desktop and narrow laptop/tablet widths:

- empty, loading, populated, partial/degraded, validation, conflict, and server-error;
- short and long names/criteria/feature differences;
- no screenings, mixed eligibility, and all dropout workflow states;
- multiple clusters, all-noise/degraded cohort, selected patient, and tied neighbors;
- keyboard focus, zoom controls, dialogs/drawers, and graph/list selection;
- normal and reduced motion;
- minimum contrast and non-color status cues;
- no unintended horizontal scrolling outside deliberate tables/canvas regions.

Visual QA is a phase exit requirement, not a handoff footnote. If browser tooling is unavailable,
the stage remains open rather than being described as visually accepted.

### 10.3 Performance budgets

- Avoid route-wide refetch loops and N+1 research context requests.
- Keep the 750-node Atlas responsive during pan, zoom, hover, and selection on the project target
  laptop.
- Defer heavy graph work until the Cohorts route is opened.
- Preserve route-level loading feedback during document parsing and research queries.
- Record build-size impact for new icon/visualization dependencies.

## 11. Documentation changes

During implementation:

- update API documentation only for accepted additive contracts;
- update Help alongside each completed user flow, not before it exists;
- keep technical R5/R6 model/cohort documentation intact;
- update screenshots only after the relevant stage is visually accepted;
- preserve the historical patient-data plan as the semantic record;
- record any retired route redirect and removed frontend component.

## 12. Explicit non-goals

- Changing deterministic eligibility rules or learning eligibility from data.
- Retraining or replacing `xgboost-05`.
- Rebuilding or casually replacing the configured R6 active run.
- Adding live hospital/EHR workflows, enterprise administration, billing, or compliance claims.
- Adding queues, microservices, or a second frontend application.
- Replacing the controlled patient-fact catalog with unrestricted terminology entry.
- Turning the Cohort Atlas into diagnostic grouping or trial recommendation.
- Hiding required validation or missing-information states for visual simplicity.
- Adding dark mode unless the user separately expands scope.
- Starting R7 implementation before R5A acceptance.

## 13. R5A handoff format

Each stage ends with:

```text
Outcome:
Routes and flows changed:
Files changed:
Behavior/API/data changes:
Backend gaps found or resolved:
Tests and builds run:
Visual states inspected:
Known limitations:
User review requested:
Recommended next R5A stage:
```
