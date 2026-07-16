const metrics = [
  { value: '6 / 6', label: 'candidate facts and criteria matched', detail: 'Precision 1.00 · recall 1.00' },
  { value: '8 / 8', label: 'conversation states classified', detail: 'All supplied citations were valid' },
  { value: '5 / 5', label: 'unsafe requests refused', detail: 'Enrollment advice and unrelated health prompts' },
  { value: '0', label: 'provider network requests', detail: 'The measured run is fully offline' },
]

export function EvaluationPage() {
  return (
    <section className="route-entry evaluation-page">
      <header className="evaluation-hero">
        <div>
          <p className="eyebrow">Phase 8 · measured 16 July 2026</p>
          <h1>Evaluation, with the boundary visible.</h1>
          <p>
            A small, versioned held-out fixture verifies deterministic extraction structures,
            grounded conversation behavior, and representative parser latency.
          </p>
        </div>
        <div className="evaluation-stamp" aria-label="All offline acceptance checks passed">
          <strong>Passed</strong>
          <span>offline acceptance suite</span>
        </div>
      </header>

      <div className="evaluation-metrics" aria-label="Held-out evaluation metrics">
        {metrics.map((metric) => (
          <article key={metric.label}>
            <strong>{metric.value}</strong>
            <h2>{metric.label}</h2>
            <p>{metric.detail}</p>
          </article>
        ))}
      </div>

      <div className="evaluation-grid">
        <section className="evaluation-section">
          <p className="eyebrow">Deterministic coverage</p>
          <h2>Balanced synthetic result matrix</h2>
          <div className="matrix-summary" aria-label="Seeded screening state distribution">
            <span><strong>4</strong> potentially eligible</span>
            <span><strong>4</strong> likely ineligible</span>
            <span><strong>4</strong> needs review</span>
          </div>
          <p>
            The 12 seeded screenings include inclusion failures, exclusion triggers, missing
            evidence, type-1/type-2 distinction, and an exact age boundary.
          </p>
        </section>

        <section className="evaluation-section evaluation-limits">
          <p className="eyebrow">Interpretation</p>
          <h2>What the numbers do not claim</h2>
          <ul>
            <li>Extraction confidence is not eligibility confidence.</li>
            <li>The fixture is intentionally small and synthetic, not clinical validation.</li>
            <li>No hosted Groq request was used or evaluated in this run.</li>
            <li>Latency measures the deterministic parser, not end-to-end provider latency.</li>
          </ul>
        </section>
      </div>

      <section className="evaluation-method">
        <div>
          <p className="eyebrow">Reproducible method</p>
          <h2>Run the same evidence locally</h2>
        </div>
        <code>backend/.venv/bin/python -m trialsync.evaluation --iterations 20</code>
      </section>
    </section>
  )
}
