# TrialSync architecture

TrialSync is an educational, synthetic-data-only pre-screening prototype. It is not a medical device, enrollment system, or general medical assistant.

```text
reviewed text/PDF -> deterministic text extraction -> optional local Tesseract OCR
                         -> Groq candidate extraction (default when configured)
                         -> human review/approval -> structured records
structured records -> immutable patient snapshot + approved trial version
                   -> deterministic rule engine -> stored criterion evidence/result
stored screening + authoritative evidence -> bounded explanation conversation
```

The FastAPI application owns authentication, owner-scoped persistence, document review, and immutable screening history. PostgreSQL schema changes are versioned with Alembic. The React/Vite client consumes only the versioned HTTP API.

The domain engine is deliberately isolated from FastAPI, SQLAlchemy, provider clients, system time, and OCR. It evaluates typed facts and approved rule JSON only. Missing, stale, conflicting, unsupported, and unit-incompatible information stays `unknown`; a provider cannot approve data or change the final state.

Imports are bounded to 1 MB of pasted text or 5 MB/10 PDF pages. PDFs first use embedded text. If that is insufficient, local Tesseract OCR runs after Poppler rasterization at 200 DPI with timeouts. OCR source text remains page-local, is marked in the review UI, and is never trusted without human approval. Groq receives only the bounded synthetic source text and must return schema-validated candidates with exact, verified quotations. Provider failure falls back to deterministic candidates.

The screening conversation is scoped to one authorized saved screening. The server rebuilds authoritative context each request, validates citations, persists at most ten messages, and rejects unsupported, advice, cross-record, and prompt-injection requests. Conversation content is never evidence.
