# TrialSync

TrialSync is an academic full-stack prototype for explainable clinical-trial pre-screening using synthetic data only. Phase 2 provides demo-user authentication, user-owned structured patient facts, and versioned trial criteria. It does not run screenings yet.

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

Open `http://localhost:5173`. The API documentation is at `http://localhost:8000/docs`. Health endpoints are:

- `GET http://localhost:8000/health/live` — process liveness only.
- `GET http://localhost:8000/health/ready` — database connectivity and migration status.

The browser API base URL comes from `VITE_API_BASE_URL` in the root `.env`; backend settings come from `DATABASE_URL` and `TRIALSYNC_*` variables. No credentials belong in Git.

## Phase 2 workflow

1. Register a demo account at `/register` or sign in at `/login`.
2. Add fictional patients at `/patients`, then open one to record conditions, medications, observations, and demographics.
3. Add fictional trials at `/trials`, open one, create a draft version, and add ordered inclusion or exclusion criteria.

All patient and trial queries are scoped to the authenticated owner. List endpoints are intentionally limited to 100 records for the semester demo. Only synthetic data may be entered.

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
```

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
| 3. Deterministic screening engine | Not started | Deliberately outside this milestone |

This is an educational prototype, not a medical device, clinical decision system, or production hospital service.
