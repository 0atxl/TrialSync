# Phase 7 held-out synthetic evaluation

This report covers only fictional fixtures in `phase7_heldout.json`. The fixture wording is separate from the examples in the build specification. It evaluates application behavior, not biomedical model training or clinical validity.

## Local baseline and mocked-provider result

Run date: 2026-07-16 (Asia/Kolkata).

| Measure | Result | Evidence |
|---|---:|---|
| Deterministic extraction candidate precision | 6/6 expected candidates (100%) | Four held-out patient/trial fixtures plus exact source-span checks |
| Deterministic extraction candidate recall | 6/6 expected candidates (100%) | Expected concepts/criteria in the held-out fixture |
| Exact structured-record accuracy | 4/4 fixture structures (100%) | Provider/local Pydantic validation tests |
| Invalid-output detection | 3/3 invalid classes rejected | Missing required field, malformed JSON, and hallucinated quotation |
| Source-quotation verification failures accepted | 0 | Hallucinated quotation is rejected before review persistence |
| Supported-message accuracy | 2/2 (100%) | Summary and missing-information questions |
| Citation precision | 1/1 valid; 1/1 fabricated rejected | Exact criterion/evaluation/evidence ID validation |
| Unsupported-claim count | 0 in tested responses | Unsupported question becomes `insufficient_evidence` |
| Refusal accuracy | 5/5 (100%) | Advice, diagnosis, enrollment, cross-record, and injection cases |
| Follow-up/history boundary | Latest 10 exactly | Six exchanges leave five chronological pairs |
| Provider failures | Explicit and non-persistent | Timeout, 429, provider error, malformed response, and disabled mode |
| Provider request count | 0 live / mocked calls only | Automated tests never call the network |

Rule-based extraction records measured per-request latency in `quality.nlp.latency_ms`. Groq responses additionally record prompt/model IDs, validation outcome, token usage, and latency without storing raw payloads or source documents in logs.

## Hosted Groq evaluation status

No `GROQ_API_KEY` was configured for this run, so no hosted request was made and no live latency or hosted-model quality number is claimed. The adapter was exercised through deterministic HTTP mocks for valid strict-schema output, invalid schema, malformed JSON, hallucinated quotation, timeout, 429, and provider error paths.

The configured default `openai/gpt-oss-20b` was checked against the official Groq documentation on 2026-07-16: it is listed as a production model and supports strict JSON-schema structured outputs. Model availability remains configuration-driven because hosted model IDs can change.

## Acceptance interpretation

The deterministic baseline and canonical explainer pass the held-out fixture. The hosted adapter is safe to enable for synthetic demonstration data, but live model quality and latency must be rerun with an authorized course/demo account before presenting hosted-provider measurements. All hosted extraction output remains an unapproved candidate, and all chat citations remain subject to server-side validation.
