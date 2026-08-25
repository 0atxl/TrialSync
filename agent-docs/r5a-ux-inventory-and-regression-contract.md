# TrialSync R5A-0 UX Inventory and Regression Contract

**Date:** 2026-08-25
**Status:** Accepted by the user on 2026-08-25.
**Parent plan:** [`r5a-frontend-experience-redesign-plan.md`](r5a-frontend-experience-redesign-plan.md)

## 1. Purpose

Record the complete pre-redesign frontend surface so R5A can simplify presentation without losing
working behavior. Every current route, major action, form, overlay, API dependency, and critical
test contract is assigned one of these outcomes:

- **Retain:** behavior and location remain substantially the same.
- **Consolidate:** behavior remains but joins a shared component or flow.
- **Move:** behavior remains but changes route or hierarchy.
- **Replace:** behavior remains while the interaction/presentation is rebuilt.
- **Retire:** presentation or action is removed because it is redundant or implementation-facing.

This document is a regression contract, not a mandate to preserve current copy or layout.

## 2. Evidence reviewed

- 21 current route definitions, including public, protected, error, and wildcard routes.
- 22 route-page components plus shared authentication, layout, editor, dialog, toast, screening,
  chat, and research components.
- All frontend API calls and corresponding backend route declarations.
- Current frontend tests: 68 main application tests after the R5A-0 characterization additions,
  13 focused research/toast tests, 2 configuration tests, and 6 browser journeys.
- Current responsive/focus/reduced-motion CSS contracts.
- The completed patient-data entry plan and the accepted R5/R6 integration contracts.
- User review feedback supplied on 2026-08-23 and the approved R5A decisions on 2026-08-25.

Browser-controlled screenshots could not be captured during this audit because the configured
browser runtime failed during initialization. The user has already reviewed the running interface
directly and supplied the visual/interaction findings that initiated R5A. No automated screenshot
acceptance is claimed for this preflight.

## 3. Quantified current-state findings

- 69 repeated `eyebrow` labels appear across pages/components.
- 20 route headers use the same `page-heading` treatment whether or not the page needs explanatory
  copy.
- 15 forms use several different surrounding patterns.
- 4 native dialog definitions support multiple complex editors and confirmations.
- 6 inline `details` disclosures use unrelated presentation conventions.
- `styles.css` is 2,454 lines with media rules spread across several historical sections and
  overlapping 680/760/900/980/1040/1050px breakpoints.
- Dashboard data comes only from the first 100 full screening records.
- Patient and trial manual creation and import are separate entry routes and separate visual
  workflows.
- Catalog administration is conditionally hidden from primary navigation; live RxNorm/LOINC
  suggestions are currently administrator-only.
- Screening detail correctly prioritizes eligibility at the top, but research tools, snapshot,
  evidence, assistant, metadata, and explanatory copy create a long page with competing regions.
- Research pages expose model names, feature-space terms, algorithm names, run IDs, member UUIDs,
  parameters, indexes, and display coordinates in the default view.
- The Atlas draws all points in a fixed SVG but has no pan/zoom, search, cluster hulls, keyboard
  node interaction, or neighbor edges.

## 4. Route disposition inventory

| Current route | Current responsibility | Current APIs | R5A disposition | Destination/stage |
|---|---|---|---|---|
| `/login` | Login, password reveal, demo-credential fill | `POST /auth/login` | Replace presentation; retain authentication and password behavior | R5A-1 compact login |
| `/register` | Account creation | `POST /auth/register` | Replace presentation; retain registration behavior | R5A-1 compact registration |
| `/` | Screening distribution, recent screenings, new/batch actions | `GET /screenings` | Replace | R5A-2 Overview dashboard |
| `/patients` | Searchable patient list; separate import/add actions | `GET /patients` | Replace list; consolidate creation actions | R5A-3/4 Patients |
| `/patients/new` | Basic manual profile followed by separate detail editing | `POST /patients` | Replace while retaining route compatibility | R5A-3 unified Add patient, manual source |
| `/patients/:patientId` | Demographics, consistency, facts, unsupported details, activity, deletion | Patient/catalog/activity/fact APIs | Replace hierarchy; retain all mutations and warnings | R5A-4 patient detail |
| `/trials` | Searchable trial list; separate import/add actions | `GET /trials` | Replace list; consolidate creation actions | R5A-3/4 Trials |
| `/trials/new` | Basic manual trial followed by separate criteria editing | `POST /trials` | Replace while retaining route compatibility | R5A-3 unified Add trial, manual source |
| `/trials/:trialId` | Profile, hidden draft/version lifecycle, criteria, deletion | Trial/version/criterion APIs | Replace hierarchy; retain backend version lifecycle | R5A-4 trial detail |
| `/imports/new?kind=patient|trial` | Choose pasted text/PDF and create import review | `POST /imports` | Move behind Add patient/Add trial source choice; retain redirect | R5A-3 ingestion source step |
| `/imports/:importId` | Split source/candidate review and approval | Import read/update/approve/delete | Replace with canonical entity review steps; retain direct recovery route | R5A-3 shared review |
| `/screenings` | Search/filter history, new and batch actions | `GET /screenings` | Replace presentation; retain capabilities | R5A-4 Screenings |
| `/screenings/new` | Patient/trial selects and deterministic screening | Patient/trial lists, `POST /screenings` | Consolidate selectors and context | R5A-4 New screening |
| `/screenings/:screeningId` | Eligibility, snapshot, research, evidence, chat, report, metadata | Screening/chat/report/R5/R6 APIs | Replace hierarchy; retain all results and independent actions | R5A-4/5 screening detail |
| `/batches/new` | Multi-select bounded patient × trial screening | Patient/trial lists, `POST /screening-batches` | Move under Screenings; retain route/limits | R5A-4 Batch screening |
| `/batches/:batchId` | Matrix, filter, links, CSV export | `GET /screening-batches/:id` | Replace presentation; retain matrix/export | R5A-4 Batch result |
| `/catalog` | Admin concept CRUD, RxNorm/LOINC suggestions, retire/restore | Clinical-concept APIs | Move out of primary navigation; retain admin route | R5A-1/7 Administration |
| `/research/recruitment` | Trial screening counts and linked prediction bands | `GET /research/trial-overview` | Replace and merge into Dropout dashboard; preserve redirect | R5A-5 `/research/dropout` |
| `/research/cohorts` | Static PCA SVG, filters, member list/detail, similarity, screening overlay | Cohort/similarity APIs | Replace interaction completely; retain route | R5A-6 Cohort Atlas |
| `/help` | Core workflow, logic, assistant, data boundary, verification | none | Replace content and information architecture | R5A-7 Help |
| wildcard/error routes | Recoverable route/application failures | none | Consolidate with shared state treatment | R5A-1 shared errors |

## 5. Action inventory

### 5.1 Global and list actions

| Current action | Current locations | Disposition |
|---|---|---|
| New screening | Overview, Screenings, patient contextual note | Keep in Screenings; retain patient-context shortcut only after relevant patient action |
| Batch screening | Primary navigation, Overview, Screenings | Remove from primary navigation and Overview; keep as secondary Screenings action |
| Add patient | Patients | Keep as sole primary Patients action; source choice follows |
| Import patient | Patients | Merge into Add patient source choice |
| Add trial | Trials | Keep as sole primary Trials action; source choice follows |
| Import trial | Trials | Merge into Add trial source choice |
| Catalog | Admin-only primary navigation | Move to account/administration entry |
| Research recruitment/cohorts | Research subnavigation | Replace with Dropout/Cohorts subnavigation |
| Sign out | Sidebar footer | Retain with revised shell treatment |

### 5.2 Record actions

| Area | Actions that must remain | Presentation change |
|---|---|---|
| Patient | edit demographics; add/edit/remove/restore detail; record unsupported detail; delete; inspect activity | Simplify default detail; use one consistent focused editor and secondary activity region |
| Trial | edit profile; start criteria edit; add/edit/remove criterion; retain unsupported criterion; save protocol; delete | Hide draft/version mechanics; present one current criteria editing state |
| Screening | download report; inspect evidence; ask/clear assistant; start/continue dropout; cohort context; similarity | Group under result/evidence/research sections; remove competing card grid |
| Batch | select patients/trials; run; filter matrix; open screening; export CSV | Keep under Screenings with compact toolbar and matrix |
| Catalog admin | add concept; terminology lookup/select; change screening availability; retire/restore | Move to Administration and reuse shared field/toolbar patterns |

## 6. Form and overlay inventory

| Current surface | Current pattern | Problem | R5A destination |
|---|---|---|---|
| Login/register | Centered split content/form panel | Repeated marketing-style intro and demo copy | Compact authentication panel in R5A-1 |
| New patient | One profile form plus duplicate-name dialog | Clinical details require a second page after save | Patient step flow in R5A-3 |
| Patient demographics | Inline edit inside detail page | Behavior is good; visual pattern is page-specific | Shared summary/edit section in R5A-4 |
| Clinical detail editor | Large native dialog with catalog browse/search and dynamic controls | Complex dialog competes with underlying page; catalog interaction differs from ingestion | Shared focused detail step/drawer in R5A-3/4 |
| Patient removal/delete | Confirmation dialogs, reason form, Undo toast | Behavior is correct | Retain through shared confirmation primitive |
| New trial | One profile form, then criteria on detail route | Creation is split and incomplete-feeling | Trial step flow in R5A-3 |
| Trial profile | Inline edit | Behavior is sufficient | Shared summary/edit section in R5A-4 |
| Criterion editor | Large native dialog with browse/search and dynamic controls | Different interaction from imported criteria and exposes mapping mechanics | Shared criteria row editor in R5A-3/4 |
| Import source | Dedicated route with radio source toggle | Disconnected from Add patient/Add trial | First step of each entity flow |
| Import review | Dense split source pane plus editable candidate cards | Raw fact fields and rule JSON overwhelm the flow | Same canonical Basics/Details/Criteria review steps as manual entry |
| Single screening | Two native select controls | Becomes cumbersome as lists grow | Searchable patient/trial selection in R5A-4 |
| Batch screening | Two long checkbox columns | Functional but dense | Filterable multi-select lists in R5A-4 |
| Assistant | Inline transcript and composer; confirmation dialog | Functionality is strong; page competes for width | Retain in collapsible/secondary evidence region |
| Dropout enrollment | Seven baseline inputs shown after technical model strip | Too much context and implementation copy at once | Baseline stage in R5A-5 |
| Dropout events | Four expandable independent forms | Input types are valid but workflow state is unclear | Event summary with focused Add actions in R5A-5 |
| Snapshot readiness | Four checkboxes plus snapshot terminology | Backend concept exposed as user task | Day-30 review completion stage in R5A-5 |
| Catalog concept creation | Persistent admin form beside list | Ordinary users cannot use suggestions inline | Admin remains; routine inline suggestions added in R5A-3 |

## 7. Component disposition

### Retain behavior

- `AuthContext` and `ProtectedRoute`.
- `ToastProvider`, queueing, actions, announcements, and reduced-motion behavior.
- unsaved-change hook/dialog behavior.
- biological-sex control semantics and keyboard behavior.
- patient catalog-driven validation and server-authoritative mutation state.
- `ScreeningChatPanel` request/citation/refusal/retry semantics.
- deterministic `StateDistribution` calculation, although chart presentation may be replaced.
- report download behavior.

### Consolidate or rebuild presentation

- `AppLayout` into the approved six-item navigation shell.
- `ConfirmationDialog` and editor overlays into shared dialog/drawer primitives.
- `ClinicalDetailEditor` and `TrialCriterionEditor` around shared concept search and field anatomy.
- patient/trial record tables around one responsive list/table primitive.
- page headings, list toolbars, empty/loading/error states, and technical-details disclosures.
- `PatientActivity` into a secondary bounded history region.
- `ResearchNav` into Dropout/Cohorts navigation.
- `ResearchRiskPanel` into the three-stage dropout flow.
- `ResearchToolsPanel` into compact independent actions/results.
- static Atlas plot/table/inspector into the interactive Atlas shell.

### Retire after replacement

- letter navigation glyphs;
- generic `workspace-page` copy patterns and repeated page eyebrows;
- the separate primary-navigation Batch item;
- ordinary Catalog navigation;
- separate Import buttons on patient/trial list headers;
- default model/run/vector/member-ID metadata lines;
- the current recruitment page as a standalone destination after redirect compatibility exists;
- obsolete one-off CSS only after the owning component is replaced and verified.

## 8. User-visible content relocation

### Keep near the task

- field-specific validation and conflict resolution;
- missing screening evidence and criterion reasons;
- explicit reviewed-none day-30 confirmation where zero has meaning;
- one concise statement that research output does not change screening;
- provider/OCR details only when they explain an actionable failure;
- destructive-action consequences before confirmation.

### Move to Technical details

- screening engine/DSL/terminology/unit versions;
- model candidate/version, precise threshold, artifact state, and numeric contribution values;
- active cohort run, representation versions, DBSCAN parameters, exact index metadata, PCA
  coordinates, vector checksums, and member IDs;
- import extractor provider/model and page/character diagnostics unless needed to resolve an error;
- trial protocol history/version identifiers.

### Move to Help

- academic/synthetic project scope and data boundary;
- complete manual/import instructions;
- deterministic engine explanation;
- report and assistant boundaries;
- dropout observation window, model method, threshold policy, and factor methodology;
- cohort grouping, map approximation, similarity methodology, and limitations;
- versioning, reproducibility, and technical verification details.

### Remove rather than relocate

- generic slogans and punchlines;
- paragraphs that merely restate the page title;
- repeated statements of the same immutable/research boundary;
- visible UUIDs or hashes with no user action attached;
- “AI-powered” or similar vague value claims.

## 9. API sufficiency and exact backend gaps

### 9.1 Existing APIs are sufficient for

- login, registration, and owner-scoped access;
- patient creation/edit/delete, controlled details, unsupported review items, activity, void,
  restore, and consistency rules;
- trial creation/edit/delete and the internal draft/approved protocol lifecycle;
- import creation, source review, candidate update, approval, rejection, OCR, and provider fallback;
- single and batch deterministic screening, saved evidence, PDF report, and explanation chat;
- dropout enrollment, event capture, day-30 readiness, prediction, and trial aggregate counts;
- R6 run discovery, all PCA points, member filtering/detail, saved-screening projection, and exact
  similarity.

Manual/import convergence is primarily frontend state and routing work. It does not require a new
patient/trial persistence model or a combined backend wizard.

### 9.2 Gap B1 — Overview summary

Current `/screenings` is limited to 100 records and loads presentation-rich screening responses. It
cannot efficiently or completely provide the approved activity series, dropout workflow status,
attention items, and recent summaries.

Smallest accepted addition:

```text
GET /api/v1/overview
```

R5A-4 also added optional `patient_id` and `trial_id` query filters to the existing owner-scoped
`GET /api/v1/screenings` route. This keeps patient/trial related-screening sections within the
existing 100-row bound without changing the response shape or persistence model.

Owner-scoped response:

- eligibility counts;
- bounded daily screening activity;
- dropout workflow counts for potentially eligible screenings;
- bounded attention items;
- recent screening summaries.

No dashboard state is persisted.

### 9.3 Gap B2 — Dropout worklist

Current `/research/trial-overview` returns aggregates only. Building one row per potentially
eligible screening would require loading screenings and then issuing one risk-context request per
row.

Smallest accepted addition:

```text
GET /api/v1/research/dropout-overview
```

Owner-scoped response per potentially eligible screening:

- screening, patient display, and trial display references;
- follow-up state: not started, information needed, ready, or predicted;
- latest probability summary when present;
- updated timestamp and next-action code;
- aggregate workflow and prediction-band counts.

All linkage continues through the version-matched research enrollment and active model. Missing
prediction remains missing, never `0%`.

### 9.4 Gap B3 — Routine inline terminology suggestions

The active local catalog is readable by every authenticated user, but external terminology suggestions were
restricted to catalog administrators. R5A needs inline suggestions without allowing a
routine user to silently create screening concepts.

Smallest accepted addition:

```text
GET /api/v1/patient-fact-catalog/suggestions
```

Rules:

- available to authenticated users;
- returns active local matches first and optional advisory condition, RxNorm, and LOINC matches;
- selecting an active local match uses the existing catalog-backed mutation contract;
- selecting an external-only match opens one compact setup dialog with its inferred category and
  suggested unit where available;
- routine users can keep it as a review-only unsupported detail/criterion;
- catalog administrators can explicitly promote it through the existing catalog API and continue
  into the normal value or criterion editor;
- provider unavailability leaves local catalog search functional.

### 9.5 Gap B4 — Human cohort presentation

Current R6 payloads expose generic labels and member IDs but no stable human display name or
plain-language group/member summary.

Smallest accepted additions to existing R6 responses:

- `display_name` for every reference member and saved-screening overlay;
- human `group_label` separate from the stable technical cluster label;
- bounded `group_characteristics` derived after clustering;
- bounded `shared_characteristics` and `meaningful_differences` for selected members/overlays;
- readable criterion context for screening-profile comparisons.

Display names use existing generated source metadata where available; otherwise a versioned
deterministic fictional-name sidecar is added. These fields do not alter vectors, PCA, clustering,
indexes, member order, or the configured active run.

### 9.6 Explicitly rejected backend work

- no eligibility-engine changes;
- no unified “wizard” persistence service;
- no new patient/trial draft tables;
- no duplicate dashboard persistence;
- no `xgboost-05` retraining or replacement;
- no R6 feature, cluster, PCA, or FAISS regeneration for presentation;
- no graph database or graph API;
- no queue, cache service, or microservice;
- no automatic canonical concept creation from external terminology.

## 10. Regression contract

| Capability | Current protection | R5A requirement |
|---|---|---|
| Authentication and protected redirects | Main frontend tests | Preserve through R5A-1 |
| Password reveal and registration | Main frontend tests | Preserve through R5A-1 |
| Overview distribution and recent-screening links | New R5A-0 characterization test | Replace data source/presentation intentionally in R5A-2 |
| Catalog admin authorization | New R5A-0 characterization plus admin mutation tests | Preserve after moving navigation |
| Patient search and creation | Main frontend tests | Preserve in unified R5A-3/4 flow |
| Duplicate-name review | Main frontend tests | Preserve in review step |
| Biological-sex/date validation | Main frontend/backend tests | Preserve exactly |
| Patient edit/conflict/unsaved state | Main frontend/backend tests | Preserve exactly |
| Catalog-driven add/edit/unknown/duplicate/error | Main frontend/backend tests | Preserve exactly |
| Pregnancy consistency | Main frontend/backend tests | Preserve exactly |
| Void/restore/activity/delete | Main frontend/backend tests | Preserve exactly |
| Trial search and both creation sources | New R5A-0 characterization plus import tests | Merge sources without losing either |
| Guided and unsupported criteria | Main frontend/backend tests | Preserve without routine rule JSON |
| Import text/PDF/review/approval/rejection/errors | Main frontend and browser tests | Preserve in common entity flow |
| Single deterministic screening | Main frontend/backend/browser tests | Preserve exactly |
| Batch limits/matrix/export | Main frontend/backend/browser tests | Preserve after navigation move |
| Evidence/missing/configuration states | Main frontend/backend/browser tests | Preserve exactly |
| PDF report | Main frontend/backend tests | Preserve exactly |
| Explanation chat/citations/retry/refusal/clear | Main frontend/backend/browser tests | Preserve exactly |
| R5 enrollment/events/readiness/prediction | Focused research tests | Preserve in staged UX |
| R5 missing-not-zero invariant | Focused frontend/backend tests | Preserve exactly |
| Trial risk aggregates | Focused frontend/backend tests | Reconcile into dropout worklist |
| R6 saved-screening cohort/similarity independence | Focused frontend/backend tests | Preserve exactly |
| R6 two representations/exact neighbors/overlay | Focused frontend/backend tests | Preserve in graph interaction |
| Loading/error/degraded states | Main/research/browser tests | Preserve and unify presentation |
| Keyboard/focus/reduced motion | Main/toast/browser tests | Extend to new components/graph |

New tests needed during later stages—not R5A-0—are bounded to the new behavior:

- navigation redirects and six-item shell;
- Overview endpoint/charts/filter links/degraded research;
- unified manual/import step state and inline terminology suggestions;
- Dropout worklist and three-stage flow;
- Atlas pan/zoom/search/filter/focus/selection/neighbor edges and 750-node responsiveness;
- Technical-details visibility and user-visible copy audit.

## 11. Low-fidelity page structures

These structures lock hierarchy, not final spacing or styling.

### 11.1 Overview

```text
┌ Overview ───────────────────────────────────────────────┐
│ [Eligibility distribution — clickable stacked chart]  │
│                                                       │
│ [Screening activity chart]  [Dropout workflow chart]  │
│                                                       │
│ Needs attention                 Recent screenings      │
│ • Patient / issue / action      Patient · Trial · State│
│ • Trial / issue / action        Patient · Trial · State│
└───────────────────────────────────────────────────────┘
```

No New screening or Batch action appears here; navigation and the Screenings page own those tasks.

### 11.2 Unified patient/trial ingestion

```text
┌ Add patient / Add trial ───────────────────────────────┐
│ 1 Source ── 2 Basics ── 3 Details/Criteria ── 4 Review│
│                                                       │
│ Source: [Manual entry] [Import document]               │
│                                                       │
│ Current step content                                  │
│ • shared field rows                                   │
│ • inline concept suggestions                          │
│ • field-level validation                              │
│                                                       │
│ [Back]                                  [Continue]     │
└───────────────────────────────────────────────────────┘
```

For imported sources, the original span is available beside or below the field on demand; it does
not create a separate raw-field editor.

### 11.3 Screening detail

```text
┌ Patient name · Trial name                 [Report] ────┐
│ ELIGIBILITY RESULT      pass / fail / unknown counts   │
├───────────────────────────────────────────────────────┤
│ Criteria filters: [Needs review] [Failed] [Passed]     │
│ Criterion row → reason, evidence, missing information  │
│ Criterion row → reason, evidence, missing information  │
├───────────────────────────────────────────────────────┤
│ Research                                                │
│ Dropout status/action | Cohort context | Similar people│
├───────────────────────────────────────────────────────┤
│ [Ask about result]              [Technical details]    │
└───────────────────────────────────────────────────────┘
```

Eligibility and criterion evidence remain above research. Chat and provenance are secondary.

### 11.4 Dropout dashboard and individual flow

```text
Research: [Dropout] [Cohorts]

┌ Workflow summary ──────────────────────────────────────┐
│ Not started | Information needed | Ready | Predicted   │
│ [interactive distribution for predicted records]      │
├───────────────────────────────────────────────────────┤
│ Search / Trial / Status filters                        │
│ Patient | Trial | Follow-up | Estimate | Updated | →   │
│ Patient | Trial | Follow-up | —        | Updated | →   │
└───────────────────────────────────────────────────────┘

Individual screening:
[1 Baseline] ── [2 Day-30 information] ── [3 Estimate]
Current step content + one primary next action
```

### 11.5 Cohort Atlas

```text
Research: [Dropout] [Cohorts]

┌ Search ─ Perspective ─ Filters ─ Fit/Reset ────────────┐
│                                             │ Patient  │
│       ○ ○○                                  │ Name     │
│    ╭ cluster region ╮      · noise          │ Group    │
│    │ ○──selected──○ │                       │ Details  │
│    │  ○ ○  ○        │    ╭ group ╮          │ Similar  │
│    ╰────────────────╯    ╰────────╯          │ Diff.    │
│                                             │          │
├ legend ─ approximate map · full profile similarity ───┤
└───────────────────────────────────────────────────────┘
```

The structured patient list remains required for accessibility and narrow laptop/tablet use.

## 12. Responsive and state contract

Every later R5A stage must deliberately cover:

- desktop around 1440px;
- narrow laptop/tablet around 900–1024px;
- populated, empty, loading, error, partial/degraded, long-label, and permission states;
- keyboard-only operation and visible focus;
- reduced motion;
- non-color status cues;
- no horizontal page scrolling except an intentional batch matrix or graph canvas;
- graph/list equivalence for cohort member selection.

The current CSS demonstrates responsive intent but uses scattered breakpoints and route-specific
patches. R5A-1 must consolidate tokens/breakpoints before later pages add new layout rules.

## 13. R5A-0 completion checklist

- [x] Every current route has a disposition and destination.
- [x] Global, record, research, and administrative actions have destinations.
- [x] Every major form/dialog pattern has a replacement decision.
- [x] Existing APIs are mapped to target workflows.
- [x] Four exact backend gaps are bounded; speculative rewiring is rejected.
- [x] Existing test coverage is mapped to preserved capabilities.
- [x] Three missing route-level characterization contracts were added.
- [x] Low-fidelity structures exist for Overview, ingestion, screening detail, Dropout, and Atlas.
- [x] Current technical/repeated copy has a keep/move/remove rule.
- [x] User accepted this preflight and authorized R5A-1 on 2026-08-25.
