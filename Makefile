.PHONY: verify verify-backend verify-frontend evaluate seed-demo reset-demo test-e2e audit

verify: verify-backend verify-frontend

verify-backend:
	docker compose config --quiet
	backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
	backend/.venv/bin/pytest backend
	backend/.venv/bin/ruff check backend/src backend/tests backend/migrations
	backend/.venv/bin/mypy backend/src
	backend/.venv/bin/python -c "import trialsync.main; print('backend import ok')"
	backend/.venv/bin/python -m trialsync.evaluation --iterations 20

verify-frontend:
	npm --prefix web run lint
	npm --prefix web run typecheck
	npm --prefix web test -- --run
	npm --prefix web run build

evaluate:
	backend/.venv/bin/python -m trialsync.evaluation --iterations 20

seed-demo:
	backend/.venv/bin/python -m trialsync.demo seed

reset-demo:
	backend/.venv/bin/python -m trialsync.demo reset --yes

test-e2e:
	npm --prefix web run test:e2e

audit:
	backend/.venv/bin/pip-audit --local
	npm --prefix web audit --audit-level=high
