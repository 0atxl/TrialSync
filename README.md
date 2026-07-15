# TrialSync

TrialSync is an academic full-stack prototype for explainable clinical-trial pre-screening using synthetic data only. It connects the deterministic `pass`, `fail`, and `unknown` engine to immutable patient snapshots, approved trial versions, transactional single/batch screening history, and an evidence-first screening workspace.

## Prerequisites

- Python 3.12 or newer
- Node.js 20.19 or newer and npm
- Docker Engine with Docker Compose

## First-time setup

Run these commands from the repository root:

```bash
cp .env.example .env
```

The copied values are local placeholders. Change `POSTGRES_PASSWORD`, the matching password inside `DATABASE_URL`, and `TRIALSYNC_AUTH_SECRET` if this database is accessible beyond your machine. The auth secret must contain at least 32 characters.

Start PostgreSQL and wait for its health check:

```bash
docker compose config --quiet
docker compose up -d --wait db
```

Create the backend environment, install the pinned project dependencies, and apply migrations:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -e './backend[dev]'
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
```

Install the frontend dependencies from the checked-in lockfile:

```bash
npm --prefix web ci
```

## Run locally

Use two terminals from the repository root.

Backend:

```bash
backend/.venv/bin/uvicorn trialsync.main:create_app --factory --app-dir backend/src --reload
```

Frontend:

```bash
npm --prefix web run dev
```

Open `http://localhost:5173` (or `http://127.0.0.1:5173`). The API documentation is at `http://localhost:8000/docs`. Health endpoints are:

- `GET http://localhost:8000/health/live` — process liveness only.
- `GET http://localhost:8000/health/ready` — database connectivity and migration status.

The browser API base URL comes from `VITE_API_BASE_URL` in the root `.env`; backend settings come from `DATABASE_URL` and `TRIALSYNC_*` variables. No credentials belong in Git.

## Phase 2 workflow

1. Register a demo account at `/register` or sign in at `/login`.
2. Add fictional patients at `/patients`, then open one to record conditions, medications, observations, and demographics.
3. Add fictional trials at `/trials`, open one, create a draft version, and add ordered inclusion or exclusion criteria.

All patient and trial queries are scoped to the authenticated owner. List endpoints are intentionally limited to 100 records for the semester demo. Only synthetic data may be entered.

## Phase 3 deterministic engine

The pure package at `backend/src/trialsync/domain` evaluates immutable typed inputs without importing FastAPI, SQLAlchemy, PostgreSQL drivers, hosted providers, ML packages, or the system clock. Callers supply the screening date explicitly:

```python
from trialsync.domain import screen

result = screen(patient_snapshot, approved_trial_version, screening_context)
```

The versioned `1.0` rule DSL supports:

- `and`, `or`, and `not` with three-valued logic.
- `present`, `absent`, `concept_is`, and `concept_in`.
- `eq`, `lt`, `lte`, `gt`, `gte`, and inclusive `between` comparisons.
- `current` and `within_before` temporal wrappers.
- `latest` and `any` numeric selection.

Missing, stale, conflicting, unsupported, or unit-incompatible evidence returns `unknown`; it never silently passes. Inclusion and exclusion criteria share the same raw truth evaluation but convert truth to results according to criterion kind. Any required failure produces `likely_ineligible`, all required passes produce `potentially_eligible`, and every other required-result combination produces `needs_review`.

The API uses JSON bearer-token authentication:

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me

GET|POST           /api/v1/patients
GET|PATCH|DELETE   /api/v1/patients/{patient_id}
POST               /api/v1/patients/{patient_id}/facts
PATCH|DELETE       /api/v1/patients/{patient_id}/facts/{fact_id}

GET|POST           /api/v1/trials
GET|PATCH|DELETE   /api/v1/trials/{trial_id}
POST               /api/v1/trials/{trial_id}/versions
PUT|DELETE         /api/v1/trials/{trial_id}/versions/{version_id}
POST               /api/v1/trials/{trial_id}/versions/{version_id}/criteria
PUT|DELETE         /api/v1/trials/{trial_id}/versions/{version_id}/criteria/{criterion_id}

POST               /api/v1/screenings
GET                /api/v1/screenings
GET                /api/v1/screenings/{screening_id}
POST               /api/v1/screening-batches
GET                /api/v1/screening-batches
GET                /api/v1/screening-batches/{batch_id}
```

## Phase 4 screening history

`POST /api/v1/screenings` accepts a user-owned `patient_id`, an approved
`trial_version_id`, and an optional ISO screening date. It creates or reuses an
immutable patient snapshot, runs the same pure Phase 3 engine, and stores every
criterion result, evidence reference, rejected evidence item, missing-information
requirement, and version field in one transaction.

Deleting a patient after screening detaches the identity record but keeps its
immutable snapshot and screening history. A trial referenced by a saved screening
cannot be deleted. Editing current patient or trial labels never rewrites a stored
criterion outcome.

`POST /api/v1/screening-batches` accepts unique or repeated
`patient_snapshot_ids` and approved `trial_version_ids`. IDs are deduplicated before
the configured limits are checked (50 snapshots, 10 trial versions, and 500 pairs).
The bounded Cartesian product runs synchronously with one screening date and one
engine version, and the whole batch rolls back on unexpected persistence failure.
The response includes state totals, the total unknown-criterion count, and a normal
evidence-backed screening ID for every matrix cell.

## Phase 5 screening workspace

After creating structured synthetic patients and approving a trial version, use the
workspace dashboard to run a single screening. The result page shows the immutable
patient snapshot, approved trial version, every criterion's stored source text,
canonical explanation, supporting evidence, and missing information. Unknown
criteria are shown first.

`/screenings` provides searchable, filterable history. `/batches/new` selects
previously created immutable snapshots and approved versions, previews the bounded
Cartesian pair count, and creates a synchronous batch. Each batch matrix cell links
back to the ordinary evidence-rich screening detail page. The UI is educational and
uses synthetic data only; it does not provide medical advice or enrollment guidance.

## Verification

With `.env` present, run every Phase 1 check from the repository root:

```bash
docker compose config --quiet
docker compose up -d --wait db
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/pytest backend
backend/.venv/bin/ruff check backend/src backend/tests backend/migrations
backend/.venv/bin/mypy backend/src
backend/.venv/bin/python -c "import trialsync.main; print('backend import ok')"
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web test -- --run
npm --prefix web run build
```

The backend import is intentionally side-effect free: it does not connect to PostgreSQL, create tables, or load models. Schema changes are made only through Alembic.

## Current scope

| Phase | Status | Evidence |
|---|---|---|
| 0. Clean repository | Complete | Planning documents and agent instructions are committed |
| 1. Foundation | Complete | Migration, health/config tests, routed frontend tests, type check, lint, and build |
| 2. Authentication and structured data | Complete | Owner-scoped auth, patient/fact and trial/version/criterion API and UI tests |
| 3. Deterministic screening engine | Complete | Pure typed engine with 43 domain golden tests and conservative unknown propagation |
| 4. Screening API and history | Complete | Immutable snapshots, stored criterion evidence, transactional single/batch history, ownership, limits, rollback, and equivalence tests |
| 5. Single and batch frontend | Complete | Dashboard, single and batch workflows, evidence detail, history filters, and linked result matrix |

This is an educational prototype, not a medical device, clinical decision system, or production hospital service.
