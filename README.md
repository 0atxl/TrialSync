# TrialSync

TrialSync is an academic full-stack prototype for explainable clinical-trial pre-screening using synthetic data only. This repository currently contains the Phase 1 project foundation: a FastAPI service, PostgreSQL migrations, and a routed React/TypeScript shell. It does not yet perform authentication, store clinical records, or run screenings.

## Prerequisites

- Python 3.12 or newer
- Node.js 20.19 or newer and npm
- Docker Engine with Docker Compose

## First-time setup

Run these commands from the repository root:

```bash
cp .env.example .env
```

The copied values are local placeholders. Change `POSTGRES_PASSWORD` and the matching password inside `DATABASE_URL` if this database is accessible beyond your machine.

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

## Verification

With `.env` present, run every Phase 1 check from the repository root:

```bash
docker compose config --quiet
docker compose up -d --wait db
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/pytest backend
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
| 2. Authentication and structured data | Not started | Deliberately outside this milestone |

This is an educational prototype, not a medical device, clinical decision system, or production hospital service.

