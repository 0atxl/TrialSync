# Clinical Catalog Management

**Date:** 2026-07-30
**Status:** Implemented locally; migrations `20260729_0009` through
`20260730_0011` are required.

## 1. Purpose

TrialSync uses one shared, PostgreSQL-backed clinical catalog for guided patient
details and trial eligibility criteria. This replaces runtime hard-coded form
definitions with local, searchable concept records while keeping deterministic
screening constrained to explicitly supported concepts.

This is an academic synthetic-data workflow, not an EHR terminology service or
a clinical decision system.

## 2. What changed

### Database catalog

`clinical_concepts` is the source of truth for routine entry metadata:

- local key and canonical local concept name;
- condition, medication, or observation category;
- status or numeric input type and permitted assertions;
- fixed observation unit where required;
- patient-entry guidance and display order;
- whether a concept is available for deterministic trial criteria;
- active/retired lifecycle state;
- optional selected terminology system and code.

Migration `20260729_0009` creates and seeds the initial 25 demo concepts. The
migration owns that frozen seed directly so future application changes cannot
alter a fresh database's migration history. Forms and APIs query PostgreSQL at
runtime; no second in-memory catalog remains in the application path.

### Routine user workflow

- Patient and trial forms search the same active catalog.
- A retired concept is no longer offered for new entry or new criteria.
- Existing facts, criteria, saved snapshots, and screening results are never
  changed by retirement.
- A concept can be recorded for patients but excluded from trial screening by
  disabling `screening_supported`.
- Trial authoring presents one current protocol through **Edit criteria** and
  **Save protocol**. Internal immutable copies remain for reproducible saved
  screenings, but drafts, revisions, ordering, and history are not routine UI
  controls.

### Administrator workflow

Migration `20260730_0010` adds `users.is_catalog_admin`. The seeded
`admin@trialsync.example` account has this capability; regular and mentor
accounts do not.

The admin-only **Catalog** page supports:

1. Search active or retired local details.
2. Add a condition, medication, or fixed-unit observation.
3. Choose whether a new concept may be used in trial criteria.
4. Retire and restore a concept.
5. Toggle trial-criteria availability without removing patient-entry support.

The management API is admin-gated:

```text
GET|POST /api/v1/clinical-concepts
GET      /api/v1/clinical-concepts/suggestions
PATCH    /api/v1/clinical-concepts/{concept_id}
POST     /api/v1/clinical-concepts/{concept_id}/retire
POST     /api/v1/clinical-concepts/{concept_id}/restore
```

## 3. Terminology suggestions

The suggestion layer is intentionally advisory. It never creates or changes a
local concept by itself, and it does not change a patient fact, criterion, or
screening result.

| Local category | Source | Behavior |
| --- | --- | --- |
| Medication | RxNav/RxNorm | Searches active approximate matches and returns name, RxCUI, source, and score. |
| Observation | LOINC Search API | Searches LOINC terms and returns a code, display name, and example UCUM unit when available. |
| Condition | None yet | Added manually; no unsafe automatic mapping is attempted. |

To use a suggestion, an administrator enters a name, chooses the category,
selects **Find RxNorm suggestion** or **Find LOINC suggestion**, reviews a
result, selects it, reviews the populated local form, then selects **Add clinical
detail**. Only that final action persists the local concept.

Migration `20260730_0011` stores the optional selected `terminology_system`
and `terminology_code` on the local concept. These are provenance, not a claim
that the local concept is clinically validated or equivalent to every use of an
external code.

### Configuration

```dotenv
TRIALSYNC_TERMINOLOGY_SUGGESTIONS_ENABLED=true
TRIALSYNC_TERMINOLOGY_TIMEOUT_SECONDS=5
TRIALSYNC_TERMINOLOGY_MAX_RESULTS=5
TRIALSYNC_LOINC_USERNAME=
TRIALSYNC_LOINC_PASSWORD=
```

RxNav has no project credential in this integration. LOINC lookup is unavailable
until a free LOINC username/password is configured; the Search API uses those values with HTTP
Basic Authentication and does not issue a separate API key. The app reports an unavailable source
and leaves manual local entry fully usable when a source is disabled, unconfigured, rate-limited,
or unreachable.

Official authentication reference: [LOINC API authentication](https://loinc.org/kb/api/auth).

## 4. Safety and product boundaries

- No real patient data should be entered into external terminology search.
- External lookup is initiated only by an administrator action.
- Suggestions are bounded, timeout-protected, and are not used by automated
  tests against live sources.
- No external match is accepted automatically.
- Retiring a concept is deliberately non-destructive.
- Existing deterministic screening invariants remain unchanged: only a saved,
  supported rule can be evaluated, and missing/ambiguous evidence remains
  `unknown`.

## 5. Verification completed

- Database/API integration tests cover admin authorization, local concept
  creation, patient entry using a new concept, safe retirement, suggestion
  review, and provenance persistence.
- Provider adapter tests use mocked RxNav and LOINC responses only.
- Frontend tests cover admin creation and explicit RxNorm selection before local
  save.
- Desktop and narrow browser inspection covered the catalog page and selected
  RxNorm confirmation state.

## 6. Next steps

### C1 — Improve local catalog governance

1. Show terminology code and source in the catalog list and filter by source.
2. Add immutable catalog activity events: created, trial availability changed,
   retired, restored, and terminology provenance selected.
3. Add a confirmation dialog and optional retirement reason.
4. Add a bounded admin export/import format for local catalog definitions.

### C2 — Review unmatched import details

1. Collect unlisted patient details and unsupported trial wording into an
   administrator review queue.
2. Suggest a local concept or create one from the queue.
3. Keep every queued item review-only until the administrator explicitly maps it.
4. Never backfill or silently rewrite existing facts, criteria, or screenings.

### C3 — Terminology quality improvements

1. Add source/version timestamps to saved provenance when a source provides
   them.
2. Add exact-code lookup and a visible external-source link for audit review.
3. Add duplicate/mismatch warnings when a local label and selected code are
   materially different.
4. Evaluate whether an approved offline LOINC subset is worthwhile for local
   development; do not make the core app depend on it.

### C4 — Deferred broader terminology scope

- Conditions require a separately reviewed terminology strategy, such as an
  approved SNOMED CT integration. Do not add broad condition auto-mapping until
  licensing, source access, clinical-review expectations, and synthetic-data
  boundaries are documented.
- Do not turn terminology search into automatic coding, medical advice, or an
  eligibility classifier.
