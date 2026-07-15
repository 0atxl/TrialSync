import { getApiBaseUrl } from '../api/config'

const foundationChecks = [
  ['API service', 'FastAPI application factory'],
  ['Data layer', 'PostgreSQL + Alembic baseline'],
  ['Web client', 'React, TypeScript, Vite'],
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
          <p className="eyebrow">Project foundation</p>
          <h1>A dependable base for evidence-first screening.</h1>
          <p className="lede">
            The service boundary, migration workflow, environment validation, and routed interface
            are ready. Clinical record workflows remain intentionally out of scope for this phase.
          </p>
        </div>
        <div className="system-stamp" aria-label="Foundation status">
          <span>01</span>
          <strong>Foundation ready</strong>
          <small>Domain features not started</small>
        </div>
      </section>

      <section className="foundation-grid" aria-labelledby="foundation-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">System map</p>
            <h2 id="foundation-heading">Verified building blocks</h2>
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

