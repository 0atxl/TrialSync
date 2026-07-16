# TrialSync Explanation Chatbot Implementation Plan

## Purpose and boundary

This plan is intentionally separate from the general product build phases. It covers only the screening-scoped explanation assistant on a saved screening result. The assistant explains authoritative stored criteria and evidence; it cannot provide medical advice, recommend enrollment or treatment, invent evidence, approve extracted candidates, or change a screening outcome.

The deterministic screening engine, canonical criterion explanations, and structured evidence table remain the source of truth and must keep working when the conversational provider is disabled or unavailable.

## Implementation status

All five milestones in this plan are implemented. The release gate is maintained by the focused backend chat tests, frontend component tests, saved-screening browser journey, production frontend build, and required visual review states. The items under “Explicitly deferred” remain intentionally outside scope.

## Current baseline

The repository already provides the Phase 7 foundation:

- user-owned conversation read, message, and clear endpoints;
- bounded persisted history and validated screening citations;
- supported, insufficient-evidence, refusal, disabled, timeout, rate-limit, and provider-error states;
- contextual suggested questions, citation links, and clear-history confirmation;
- provider-neutral canonical, mock, disabled, and Groq explanation paths.

## Implementation milestones

### 1. Conversation-shell stability

- Keep a fixed transcript viewport so the first exchange does not resize or push the screening page.
- Append the submitted user question immediately and show an accessible typing indicator while awaiting the response.
- Scroll only the transcript to its newest content; contain overscroll so the page does not move unexpectedly.
- Keep suggestions in an even responsive grid and align the text area and send button.
- Respect reduced-motion preferences for typing and scrolling.

Exit criteria: empty, first-question, populated, long-response, narrow-width, loading, and provider-error states retain a stable composer and page position.

### 2. Focus and keyboard behavior

- Support Enter to send and Shift+Enter for a newline after confirming this does not cause accidental submissions.
- Return focus to the composer after a successful response or recoverable error.
- Preserve visible focus when a citation moves the user to criterion evidence and offer a clear route back to the conversation.
- Announce new assistant responses without repeatedly reading the full transcript.

Exit criteria: the complete conversation and citation flow works with keyboard-only navigation and a screen-reader smoke test.

### 3. Contextual suggestion quality

- Generate a small deterministic base set from the stored overall state, unknown criteria, failed criteria, and missing-information requirements.
- Permit provider-suggested follow-ups only after schema validation, deduplication, length limits, and bounded-topic checks.
- Replace suggestions after each response without allowing free-form medical or enrollment guidance.

Exit criteria: suggestions are finite, relevant to the selected screening, visually consistent, and safe when Groq is unavailable.

### 4. Resilience and observability

- Preserve unsent question text after timeout, rate-limit, invalid-response, or provider failure.
- Add a bounded retry action that resubmits only with explicit user intent and never duplicates stored messages.
- Record privacy-safe latency, answer-state, provider, model, prompt-version, and validation outcome metrics without document text, questions, raw provider payloads, or secrets.

Exit criteria: each failure state has a tested recovery path and message persistence remains all-or-nothing.

### 5. Evaluation and release gate

- Extend frontend component tests for optimistic questions, the typing state, internal auto-scroll, error restoration, clear history, and disabled provider behavior.
- Add browser tests at desktop and narrow widths for empty, first exchange, long text, maximum bounded history, refusal, insufficient evidence, and provider failure.
- Verify citation grounding, latest-message trimming, ownership, prompt-injection resistance, reduced motion, focus order, and contrast.
- Run the frontend production build, full frontend tests, applicable backend chat tests, and the saved-screening end-to-end journey.

Exit criteria: all automated checks pass and the visual review confirms the transcript, suggestions, and composer remain stable in every required state.

## Explicitly deferred

- general medical chat, diagnosis, treatment, or enrollment recommendations;
- autonomous changes to evidence, criteria, review state, or screening outcome;
- streaming partial model text unless a future backend/API contract explicitly adds validated streaming;
- web, database, MCP, code-execution, or write tools for the assistant;
- unbounded history, cross-screening memory, voice, avatars, or decorative assistant personas.
