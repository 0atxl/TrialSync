import { getApiBaseUrl } from '../api/config'

const foundationChecks = [
  ['Identity boundary', 'Email/password demo accounts'],
  ['Patient records', 'Structured facts with units and provenance'],
  ['Protocol records', 'Versioned, ordered trial criteria'],
]

export function FoundationPage() {
  let apiBaseUrl: string

  try {
    apiBaseUrl = getApiBaseUrl()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Frontend configuration is invalid.'
    return (
      <section className="configuration-error" role="alert">
        <p className="eyebrow">Configuration required</p>
        <h1>TrialSync needs an API address</h1>
        <p>{message}</p>
      </section>
    )
  }

  return (
    <div className="route-entry">
      <section className="intro-panel">
        <div>
          <p className="eyebrow">Structured workspace</p>
          <h1>Review the facts before any rule is evaluated.</h1>
          <p className="lede">
            Create fictional patient records and trial protocols with explicit values, units,
            assertions, and ordered criteria. Screening remains intentionally unavailable.
          </p>
        </div>
        <div className="system-stamp" aria-label="Foundation status">
          <span>02</span>
          <strong>Records ready</strong>
          <small>Screening begins in Phase 3</small>
        </div>
      </section>

      <section className="foundation-grid" aria-labelledby="foundation-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">System map</p>
            <h2 id="foundation-heading">Available workflows</h2>
          </div>
          <span className="environment-label">API · {apiBaseUrl}</span>
        </div>

        <div className="foundation-list">
          {foundationChecks.map(([label, detail], index) => (
            <div className="foundation-row" key={label}>
              <span className="row-number">0{index + 1}</span>
              <div>
                <strong>{label}</strong>
                <p>{detail}</p>
              </div>
              <span className="row-state">Configured</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
