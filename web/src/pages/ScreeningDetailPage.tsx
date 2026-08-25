import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiDownload, apiRequest, type Screening } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ResearchToolsPanel } from '../components/ResearchToolsPanel'
import { ScreeningChatPanel } from '../components/ScreeningChatPanel'
import { ScreeningEvidence } from '../components/ScreeningEvidence'
import { useToast } from '../components/ToastProvider'
import { TechnicalDetails } from '../components/UiPrimitives'
import { isConfigurationReason, stateLabel } from './screeningHelpers'

function safeFilename(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

export function ScreeningDetailPage() {
  const { screeningId = '' } = useParams()
  const { token } = useAuth()
  const { showToast } = useToast()
  const [screening, setScreening] = useState<Screening | null>(null)
  const [error, setError] = useState('')
  const [reportDownloading, setReportDownloading] = useState(false)

  const load = useCallback(async () => {
    try {
      setScreening(await apiRequest(`/screenings/${screeningId}`, {}, token))
      setError('')
    } catch {
      setError('This screening result could not be loaded.')
    }
  }, [screeningId, token])

  useEffect(() => { void load() }, [load])

  const downloadReport = async () => {
    if (!screening || reportDownloading) return
    setReportDownloading(true)
    try {
      const blob = await apiDownload(`/screenings/${screeningId}/report.pdf`, token)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `screening-${safeFilename(screening.patient_snapshot.display_name)}-${screening.screening_date}.pdf`
      document.body.append(anchor)
      try {
        anchor.click()
      } finally {
        anchor.remove()
        window.setTimeout(() => URL.revokeObjectURL(url), 0)
      }
      showToast({
        variant: 'success',
        title: 'Report downloaded',
        message: 'The saved screening report is ready.',
      })
    } catch {
      showToast({
        variant: 'error',
        title: 'Report unavailable',
        message: 'The report could not be prepared. The saved result is unchanged.',
      })
    } finally {
      setReportDownloading(false)
    }
  }

  if (error) return <div className="form-error" role="alert">{error}</div>
  if (!screening) return <div className="loading-state">Loading screening…</div>
  if (!screening.patient_snapshot || !screening.trial_version) {
    return (
      <section className="route-entry workspace-page narrow-page">
        <Link className="back-link" to="/screenings">← Screenings</Link>
        <div className="form-error" role="alert">
          This saved screening is missing its patient or trial details.
        </div>
      </section>
    )
  }
  if (!Array.isArray(screening.evaluations) || !screening.counts) {
    return (
      <section className="route-entry workspace-page narrow-page">
        <Link className="back-link" to="/screenings">← Screenings</Link>
        <div className="form-error" role="alert">
          This saved result is incomplete and cannot be displayed safely.
        </div>
      </section>
    )
  }

  const configurationIssueCount = screening.evaluations.filter(
    (evaluation) => isConfigurationReason(evaluation.reason_code),
  ).length

  return (
    <section className="route-entry workspace-page screening-detail-page">
      <Link className="back-link" to="/screenings">← Screenings</Link>
      <header className="page-heading screening-record-heading">
        <div>
          <h1>{screening.patient_snapshot.display_name}</h1>
          <p>{screening.trial_version.title}</p>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={() => { void downloadReport() }}
          disabled={reportDownloading}
        >
          {reportDownloading ? 'Preparing report…' : 'Download report'}
        </button>
      </header>

      <section className="result-hero" aria-labelledby="eligibility-result-heading">
        <div>
          <span className="result-label">Eligibility</span>
          <h2
            id="eligibility-result-heading"
            className={`result-title state-${screening.overall_state}`}
          >
            {stateLabel(screening.overall_state)}
          </h2>
          <time dateTime={screening.screening_date}>Screened {screening.screening_date}</time>
        </div>
        <div className="counts" aria-label="Criterion counts">
          <span><strong>{screening.counts.pass_count}</strong> satisfied</span>
          <span><strong>{screening.counts.fail_count}</strong> not met</span>
          <span><strong>{screening.counts.unknown_count}</strong> review</span>
        </div>
      </section>

      {configurationIssueCount > 0 ? (
        <div className="disclaimer screening-config-alert" role="alert">
          <strong>Trial criteria need attention.</strong>{' '}
          {configurationIssueCount === 1
            ? 'One criterion could not'
            : `${configurationIssueCount} criteria could not`} be evaluated. Correct the trial
          criteria and run a new screening.
        </div>
      ) : null}

      <ResearchToolsPanel screening={screening} token={token} />
      <ScreeningEvidence evaluations={screening.evaluations} />

      <details className="assistant-disclosure">
        <summary>Ask about this result</summary>
        <ScreeningChatPanel screeningId={screening.id} />
      </details>

      <TechnicalDetails>
        <dl className="technical-details-list">
          <div><dt>Screening date</dt><dd>{screening.screening_date}</dd></div>
          <div><dt>Eligibility engine</dt><dd>{screening.engine_version}</dd></div>
          <div><dt>Rule format</dt><dd>{screening.dsl_version}</dd></div>
          <div><dt>Terminology</dt><dd>{screening.terminology_version}</dd></div>
          <div><dt>Units</dt><dd>{screening.unit_version}</dd></div>
        </dl>
      </TechnicalDetails>
    </section>
  )
}
