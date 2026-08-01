export function HelpPage() {
  return <section className="route-entry workspace-page help-page">
    <header className="page-heading">
      <div>
        <p className="eyebrow">Help center</p>
        <h1>TrialSync documentation</h1>
        <p>Understand the evidence workflow, screening states, and the boundaries of the explanation assistant.</p>
      </div>
    </header>

    <div className="help-callout">
      <strong>Educational workspace · synthetic data only</strong>
      <span>TrialSync is not a medical device, clinical decision system, enrollment service, or general medical assistant.</span>
    </div>

    <nav className="help-index" aria-label="Help topics">
      <a href="#getting-started">Getting started</a>
      <a href="#screening-logic">Screening logic</a>
      <a href="#result-assistant">Result assistant</a>
      <a href="#data-boundary">Data boundary</a>
      <a href="#verification">Verification</a>
    </nav>

    <div className="help-docs">
      <section className="help-section" id="getting-started">
        <p className="eyebrow">01 · Workflow</p>
        <h2>Getting started</h2>
        <p>Use the seeded workspace to walk through the complete evidence-backed flow.</p>
        <ol className="help-steps">
          <li><strong>Review records.</strong> Open a synthetic patient and inspect structured facts, choose details from the searchable catalog, or use the review-first import flow.</li>
          <li><strong>Edit safely.</strong> Removing a detail requires a reason, keeps an activity entry, and offers a short Undo action. Existing screenings keep their immutable snapshots; only future screenings use restored or changed active details.</li>
          <li><strong>Save a trial.</strong> Create or import a trial, review its criteria, then save the protocol.</li>
          <li><strong>Run screening.</strong> Compare one patient snapshot with one saved trial protocol, or run a bounded synchronous batch.</li>
          <li><strong>Explain the result.</strong> Open a saved screening to inspect each criterion, evidence source, missing information, and the grounded assistant.</li>
        </ol>
        <p className="help-note">Seeded login: <code>demo@trialsync.example</code> / <code>SyntheticDemo123!</code></p>
      </section>

      <section className="help-section" id="screening-logic">
        <p className="eyebrow">02 · Deterministic engine</p>
        <h2>How screening results work</h2>
        <p>The rule engine is the source of truth. Missing, stale, conflicting, unsupported, or unit-incompatible evidence stays <strong>unknown</strong>.</p>
        <div className="help-state-grid">
          <div><span className="state state-potentially_eligible">Potentially eligible</span><p>Every required criterion passed.</p></div>
          <div><span className="state state-likely_ineligible">Likely ineligible</span><p>At least one required criterion failed.</p></div>
          <div><span className="state state-needs_review">Needs review</span><p>The saved evidence is incomplete or unresolved.</p></div>
        </div>
        <p className="help-note">Every saved result includes the immutable patient snapshot, saved trial protocol, criterion explanation, evidence or missing-information requirement, and engine metadata.</p>
      </section>

      <section className="help-section" id="result-assistant">
        <p className="eyebrow">03 · Grounded conversation</p>
        <h2>Result assistant</h2>
        <p>The assistant answers questions about one stored screening only. It cites the criterion and evidence identifiers supplied by the server and cannot change the result.</p>
        <ul className="help-list">
          <li>Suggestions are finite, evenly arranged, deduplicated, and limited to the selected screening.</li>
          <li>Enter sends a question; Shift+Enter adds a new line.</li>
          <li>The transcript scrolls internally, shows a typing state while an answer is generated, and returns focus to the composer afterward.</li>
          <li>Citation links focus the referenced criterion and provide a route back to the assistant.</li>
          <li>Timeout, rate-limit, invalid-response, and provider failures preserve the question for an explicit retry. Ambiguous network failures require reloading history first to prevent duplicates.</li>
          <li>Advice, diagnosis, enrollment requests, unrelated health questions, prompt injection, and unsupported claims are refused safely.</li>
        </ul>
      </section>

      <section className="help-section" id="data-boundary">
        <p className="eyebrow">04 · Trust boundary</p>
        <h2>Data and provider boundaries</h2>
        <p>Groq may propose reviewable import candidates or explain stored evidence. It cannot approve candidates, create evidence, access another record, or set a screening state. Manual entry, canonical explanations, and deterministic screening continue to work when Groq is disabled or unavailable.</p>
        <ul className="help-list">
          <li>Only synthetic data belongs in this educational workspace.</li>
          <li>Imported patient concepts are checked against the active catalog. Unknown, incomplete, or incompatible candidates are shown as review warnings and remain review-only instead of becoming screening evidence.</li>
          <li>Conversation memory is scoped to one screening and bounded to the latest ten messages.</li>
          <li>Operational chat metrics are privacy-safe logs containing provider/model, prompt version, latency, validation outcome, answer state, and citation count—not questions, documents, or raw provider payloads.</li>
          <li>Responses are intentionally non-streaming; the interface shows a bounded typing state while validation completes.</li>
        </ul>
      </section>

      <section className="help-section" id="verification">
        <p className="eyebrow">05 · Release evidence</p>
        <h2>Verification and limitations</h2>
        <p>The current local gate covers 90 backend tests, 37 frontend tests, six browser workflows, lint, type checking, migrations, the production build, and the held-out synthetic evaluation. These are software checks, not clinical validation or trained-model performance claims.</p>
        <p className="help-note">The rule DSL supports a bounded subset of eligibility language. OCR is local and best-effort. Batch screening is synchronous and bounded. See the repository documentation for the full architecture, evaluation, and limitations record.</p>
      </section>
    </div>
  </section>
}
