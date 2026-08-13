.PHONY: verify verify-backend verify-frontend evaluate seed-demo reset-demo test-e2e audit

# Data Designer 0.8.0 and the checked 0.9.1 release cap cryptography at 49.
# See agent-docs/dependency-security-exceptions.md for the bounded exception.
PYTHON_AUDIT_IGNORES := --ignore-vuln PYSEC-2026-3552

verify: verify-backend verify-frontend

verify-backend:
	docker compose config --quiet
	backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
	backend/.venv/bin/pytest backend
	backend/.venv/bin/pytest backend/tests/research --cov=research.generate_r3_nemo --cov-fail-under=75 --cov-report=term-missing
	backend/.venv/bin/ruff check backend/src backend/tests backend/migrations backend/research
	backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/src backend/research
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
	backend/.venv/bin/pip-audit --local $(PYTHON_AUDIT_IGNORES)
	npm --prefix web audit --audit-level=moderate
