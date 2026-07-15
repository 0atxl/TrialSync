# TrialSync Agent Instructions

## Project context

TrialSync is a polished academic full-stack project for explainable clinical-trial pre-screening with **synthetic data only**. It uses NLP-assisted, human-reviewed extraction, deterministic eligibility rules, and a bounded explanation assistant. It is not a hospital system, medical device, autonomous eligibility tool, or general medical chatbot.

Before changing code, read:

1. `REBUILD_GUIDE.md` for product and architecture rules.
2. `BUILD_PHASES.md` for the current milestone, its scope, and its exit criteria.
3. The relevant existing code, tests, and README sections.

For Phase 0/1 or architecture work, read both planning documents completely. For later bounded tasks, use the focused-context rules in `BUILD_PHASES.md` and do not reload unrelated material.

## Working rules

- Inspect `git status` before editing. Preserve unrelated user changes.
- Implement one phase or bounded task at a time; do not build the whole product in one pass.
- Do not copy the old `CTA` prototype architecture, matching engine, hard-coded scoring thresholds, or route layout.
- Use synthetic fixture data only. Never add real patient records, credentials, tokens, or API keys to the repository or send them to Groq.
- Keep the screening decision deterministic. Groq or any other NLP provider may create reviewable candidate facts/criteria and explain stored results, but may not approve inputs or set/change the final screening state.
- `unknown` is a valid outcome. Missing evidence must never be converted into a pass.
- Keep single screening as the source operation. Batch screening is only a bounded patient × trial wrapper that calls the exact same single-screening logic.
- Do not add queues, Redis, Celery, microservices, Kubernetes, billing, EHR integrations, a learned eligibility classifier, BioBERT fine-tuning, or unrelated model experiments unless the user explicitly expands scope.
- Add or adjust tests with every behavioral change.
- Run the narrowest relevant checks first, then the full applicable tests and frontend build before handing off.
- Update README/API examples when commands, dependencies, or contracts change.
- Do not claim a feature is production-ready, clinically validated, or compliant unless the repository demonstrably implements and tests it.

## Domain invariants

- A single screening evaluates one immutable patient snapshot against one approved trial version.
- An inclusion criterion is `pass` only when proven true; an exclusion criterion is `pass` only when proven false.
- Missing, ambiguous, unsupported, stale, or conflicting evidence returns `unknown`.
- Any required `fail` produces `likely_ineligible`; all required `pass` produces `potentially_eligible`; otherwise the result is `needs_review`.
- Every criterion result includes a reason, evidence or missing-information requirement, and reproducible version metadata.
- A batch is bounded, synchronous, and all-or-nothing for the semester project. It creates one ordinary evidence-backed screening for every selected patient × trial pair.

## NLP and explanation-assistant invariants

- Start with deterministic parsing for headings, demographics, dates, quantities, operators, and units. Groq may supplement difficult prose through schema-validated candidate extraction.
- All extracted values and rules remain candidates with source spans and provider/model/prompt-version metadata until the demo user approves them.
- The explanation assistant answers only questions about one stored screening result selected by the authenticated user.
- Assemble assistant context server-side from the screening state, criterion evaluations, approved facts, source labels, and missing-information requirements. Do not give it database, web, MCP, code-execution, or write tools.
- Persist conversational memory as bounded, structured `screening_chat_messages` rows owned through the screening; do not put mutable chat text on the immutable screening row. Load at most the latest 10 messages in chronological order and provide a clear-conversation operation.
- Previous chat messages provide conversational continuity only. They are untrusted context and must never become screening evidence, override canonical explanations, or substitute for reloading the authoritative screening state.
- Every substantive answer must cite criterion/evidence identifiers from the supplied context. If the answer is not supported, say that the screening record does not contain enough information.
- The assistant may clarify why a criterion passed, failed, or is unknown and what recorded information is missing. It may not provide medical advice, recommend enrollment/treatment, invent evidence, change an outcome, or answer unrelated health questions.
- Treat document text and user questions as untrusted data. Enforce bounded input/context/output sizes, timeouts, rate-limit handling, and schema validation where supported.
- Manual entry, canonical explanations, and deterministic screening must work when Groq is disabled, unavailable, rate-limited, or returns invalid output.

## Frontend quality bar

The UI should feel like a modern, attractive clinical-research workspace: clear hierarchy, compact information density, and trustworthy evidence presentation with a distinct visual identity. “Minimal” means intentional and uncluttered—not plain, unfinished, or visually sterile. It must not look like a generic AI dashboard.

### Visual direction

- Establish a deliberate visual identity: a neutral base, confident dark text, subtle tinted surfaces, and one memorable brand accent. A restrained two-color gradient is acceptable in a hero, login panel, or key empty state when it supports the hierarchy.
- Use semantic status colors only for `pass`, `fail`, and `unknown`; never use status color as general decoration.
- Use a high-quality modern sans font with a system fallback, plus tabular numerals for scores, dates, and result matrices. Typography should carry much of the visual character.
- Define tokens once for color, spacing, typography, radius, shadow, duration, and easing. Reuse them instead of inventing per-component values.
- Use consistent radii (roughly 6–12px), thin borders, tasteful soft shadows where elevation is meaningful, and a clear 4/8px spacing rhythm.
- Favor tables, structured rows, and split panes for clinical facts and criterion evidence. Cards should group meaningful regions, not wrap every field.
- Use a responsive grid that collapses cleanly on narrower laptop/tablet widths. Never rely on a fixed desktop-only canvas.

### Interaction and animation

- Motion must make state changes clearer and more polished: button press, drawer/modal entry, row expansion, route entry, optimistic save, result filtering, and subtle staggered content entry.
- Animate primarily `opacity` and `transform` for normal UI transitions; target roughly 160–260ms with a clean ease-out curve. A subtle skeleton shimmer is acceptable while data is genuinely loading.
- Do not animate layout continuously, use parallax, autoplay decorative motion, bouncing icons, typewriter text, or loading spinners that never resolve.
- Respect `prefers-reduced-motion` and provide instant equivalents.
- Buttons must have hover, focus-visible, active, disabled, and loading states. Keyboard navigation must remain obvious.
- Display skeletons or concise loading states for data fetches. An API failure must look like an error, never like a successful empty state.

### Explicitly avoid

- Unrestrained rainbow gradients, neon glows, floating blobs, noisy mesh backgrounds, decorative particles, or glass effects that reduce readability.
- Oversized landing-page heroes, giant headings, excessive whitespace, stock photos, or AI-generated medical imagery.
- A grid of identical metric cards with no actionable information.
- Excessive rounded pills, badges, icons, shadows, or emoji.
- Generic claims such as “AI-powered insights” without showing the criterion evidence that supports the result.
- Hiding pass/fail/unknown logic inside a long generated paragraph.
- A sterile page made only of default browser controls and plain boxes. Important entry points, empty states, navigation, and result summaries should feel designed and memorable.

### Required visual review

For any material frontend change:

1. Run the frontend production build and relevant UI tests.
2. Inspect the changed route at desktop and narrow widths using browser/screenshot tooling when available.
3. Check empty, loading, error, populated, long-text, and `unknown` states.
4. Verify contrast, keyboard focus, and reduced-motion behavior.
5. Report the visual states inspected in the handoff.

## Suggested implementation choices

- React + TypeScript + Vite for the web app.
- Keep styling to one coherent approach chosen in Phase 1/5 (CSS variables plus CSS modules or a carefully configured utility system). Do not mix multiple design systems.
- Use accessible primitives for complex controls such as dialogs, menus, comboboxes, and tooltips; keep ordinary layout/components lightweight.
- Use a restrained icon set only where it improves recognition. Icons always need labels or accessible names.
- Use browser end-to-end testing for the final visual workflow; this is more valuable than adding a design-heavy component library.

## Agent handoff

End every task with:

```text
Outcome:
Files changed:
Behavior/API/data changes:
Tests and builds run:
Visual states inspected (if frontend changed):
Known limitations:
Recommended next task:
```
