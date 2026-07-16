# Phase 8 reproducible evaluation

Run date: 2026-07-16 (Asia/Kolkata).

This is an application evaluation using fictional fixtures only. It is not a trained-model evaluation, biomedical benchmark, clinical validation, or evidence of real-world eligibility performance.

## Reproduction

From the repository root, after setup and migration:

```bash
make seed-demo
make evaluate
make test-e2e
make audit
```

The offline evaluator reads `phase7_heldout.json`, uses the deterministic extractor and canonical explainer, and makes zero provider network requests. The seed command replaces only the fixed development demo account and refuses to run when `TRIALSYNC_ENV=production`.

## Held-out extraction and conversation results

| Measure | Result | Acceptance |
|---|---:|---|
| Extraction cases | 4/4 exact structures | Passed |
| Candidate precision | 6/6 (1.00) | Passed |
| Candidate recall | 6/6 (1.00) | Passed |
| Exact source quotation validity | 6/6 (1.00) | Passed |
| Conversation answer-state accuracy | 8/8 (1.00) | Passed |
| Supported citation validity | 2/2 (1.00) | Passed |
| Refusal accuracy | 5/5 (1.00) | Passed |
| Live provider requests | 0 | Required for automated evaluation |
| 50,000-character parser p95 | 2.729 ms across 20 samples | Passed under the 250 ms acceptance limit |

The timing is a local observation, not a service-level guarantee. The fixture documents themselves are intentionally short; the 50,000-character repeated narrative checks representative bounded-input scaling.

## Provider and safety behavior

The Phase 7 provider-mock suite remains part of `make verify`. It covers strict-schema success, malformed JSON, invalid schema, hallucinated quotations/offsets, timeout, rate limiting, provider errors, and disabled-provider fallback without making a live Groq request. Conversation tests cover supported answers, follow-up continuity, exact citation validation, fabricated-citation rejection, insufficient evidence, medical-advice/enrollment/cross-record/prompt-injection refusals, latest-10 trimming, persisted chronological reload, clear, and canonical fallback.

No `GROQ_API_KEY` was configured for this evaluation. Hosted Groq candidate quality, latency, token use, and a live success/correction comparison are therefore not claimed. When enabled for a synthetic demonstration, hosted output remains reviewable candidate data and cannot set a screening result.

## Seeded deterministic demo matrix

The repeatable development seed creates six patients, two approved trials, one 6 × 2 batch, 12 ordinary linked screenings, and eight stored chat messages.

| Required case | Seed evidence |
|---|---|
| Strong potentially eligible | Synthetic Ada Eligible |
| Inclusion failure | Synthetic Ben Inclusion Fail |
| Exclusion trigger | Synthetic Cora Exclusion Trigger |
| Missing-data needs review | Synthetic Dev Needs Review |
| Type 1 / Type 2 distinction | Synthetic Emi Type 1 Distinction |
| Numeric boundary | Synthetic Finn Age Boundary |
| Mixed batch | 4 potentially eligible, 4 likely ineligible, 4 needs review |
| Supported/refused/insufficient chat | Eight messages on the seeded needs-review result |
| PDF import | Generated machine-readable `/tmp/trialsync-phase8.pdf` fixture in the E2E preparation step |

Batch construction calls the same single-screening service for every pair. Backend equivalence tests and the browser matrix test verify that its cells are ordinary evidence-backed screening records.

## Browser verification

Five Playwright workflows run serially against local PostgreSQL, FastAPI, and Vite with rule-based extraction and canonical explanations:

1. Registration → patient → manual deterministic criterion → approval → screening → history.
2. Three patients × two approved trials → six-cell result matrix → linked evidence detail.
3. Trial text import → reviewer correction → approval → screening → criterion evidence.
4. Generated text PDF → review → approval → source provenance.
5. Seeded needs-review result → restored supported conversation → citation navigation → refresh → refusal → clear.

A sixth browser check captures loading, empty, API-error, desktop evaluation, narrow evaluation, and narrow unknown-result states. It asserts no horizontal overflow, visible keyboard focus, and the reduced-motion override.

## Interpretation and limitations

- Extraction confidence is not eligibility confidence. Screening states come only from approved structured inputs and deterministic rules.
- The held-out set is deliberately small and synthetic; perfect fixture scores should not be generalized.
- OCR, real records, external trial feeds, live hosted-provider evaluation, clinical workflow validation, and production security/compliance assessment remain out of scope.
- The application is an educational prototype, not a medical device, clinical decision system, or enrollment recommendation tool.
