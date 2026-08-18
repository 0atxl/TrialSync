# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# OCR and PDF rendering are required by the document-import workflow.
RUN apt-get update \
    && apt-get install --no-install-recommends -y fonts-liberation tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system trialsync \
    && useradd --system --gid trialsync --create-home --home-dir /app trialsync

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY README.md /app/README.md
COPY backend/src /app/backend/src
COPY backend/migrations /app/backend/migrations
COPY backend/alembic.ini /app/backend/alembic.ini

RUN pip install --no-cache-dir '/app/backend[research-runtime]' \
    && chown -R trialsync:trialsync /app

USER trialsync
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=6 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "trialsync.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
