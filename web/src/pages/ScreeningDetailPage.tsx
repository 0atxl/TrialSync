import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiDownload, apiRequest, type Evidence, type Screening } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ScreeningChatPanel } from '../components/ScreeningChatPanel'
import { ResearchToolsPanel } from '../components/ResearchToolsPanel'
import { useToast } from '../components/ToastProvider'
import { isConfigurationReason, reasonLabel, screeningTrialLabel, stateLabel } from './screeningHelpers'

const evidenceValue = (item: Evidence) => [item.value ?? 'Recorded fact', item.unit, item.effective_date].filter(Boolean).join(' · ')

export function ScreeningDetailPage() {
  const { screeningId = '' } = useParams()
  const { token } = useAuth()
  const { showToast } = useToast()
  const [screening, setScreening] = useState<Screening | null>(null)
  const [error, setError] = useState('')
  const [reportDownloading, setReportDownloading] = useState(false)

  const load = useCallback(async () => {
    try { setScreening(await apiRequest(`/screenings/${screeningId}`, {}, token)); setError('') }
    catch { setError('This screening result could not be loaded.') }
  }, [screeningId, token])
  useEffect(() => { void load() }, [load])

  const downloadReport = async () => {
    if (!screeningId || reportDownloading) return
    setReportDownloading(true)
    try {
      const blob = await apiDownload(`/screenings/${screeningId}/report.pdf`, token)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `trialsync-screening-${screeningId}.pdf`
      document.body.append(anchor)
      try {
        anchor.click()
      } finally {
        anchor.remove()
        window.setTimeout(() => URL.revokeObjectURL(url), 0)
      }
      showToast({
        variant: 'success',
        title: 'Report ready',
        message: 'The canonical screening report was downloaded.',
      })
    } catch {
      showToast({
        variant: 'error',
        title: 'Report unavailable',
        message: 'The canonical report could not be prepared. The browser evidence is unchanged.',
      })
    } finally {
      setReportDownloading(false)
    }
  }

  if (error) return <div className="form-error" role="alert">{error}</div>
  if (!screening) return <div className="loading-state">Loading result evidence…</div>
  if (!screening.patient_snapshot || !screening.trial_version) {
    return <section className="route-entry workspace-page narrow-page">
      <Link className="back-link" to="/screenings">← Screening history</Link>
      <div className="form-error" role="alert">
        This screening response is missing its presentation details. Restart the TrialSync backend
        so it loads the latest API and migration, then try again.
      </div>
    </section>
  }
  if (!Array.isArray(screening.evaluations) || !screening.counts) {
    return <section className="route-entry workspace-page narrow-page">
      <Link className="back-link" to="/screenings">← Screening history</Link>
      <div className="form-error" role="alert">
        This saved result is incomplete and cannot be displayed safely.
      </div>
    </section>
  }
  const ordered = [...screening.evaluations].sort((a, b) => Number(a.result !== 'unknown') - Number(b.result !== 'unknown') || a.criterion_order - b.criterion_order)
  const configurationIssueCount = screening.evaluations.filter((item) => isConfigurationReason(item.reason_code)).length

  return <section className="route-entry workspace-page">
    <Link className="back-link" to="/screenings">← Screening history</Link>
    <header className="result-hero"><div><p className="eyebrow">Screening result</p><h1 className={`result-title state-${screening.overall_state}`}>{stateLabel(screening.overall_state)}</h1><p><strong>{screening.patient_snapshot.display_name}</strong> · {screening.patient_snapshot.external_id}<br />{screeningTrialLabel(screening)}</p></div><div className="result-actions"><div className="counts" aria-label="Criterion counts"><span><strong>{screening.counts.pass_count}</strong> pass</span><span><strong>{screening.counts.fail_count}</strong> fail</span><span><strong>{screening.counts.unknown_count}</strong> unknown</span></div><button className="secondary-button" type="button" onClick={() => { void downloadReport() }} disabled={reportDownloading}>{reportDownloading ? 'Preparing report…' : 'Download report'}</button></div></header>
    {configurationIssueCount > 0 && <div className="disclaimer screening-config-alert" role="alert"><strong>Trial configuration needs attention.</strong> {configurationIssueCount === 1 ? 'One criterion' : `${configurationIssueCount} criteria`} could not be evaluated because the saved trial rule is invalid or unsupported. Patient information is not the problem; correct the trial draft and run a new screening.</div>}
    <section className="snapshot-panel"><div><p className="eyebrow">Immutable patient snapshot</p><h2>Patient facts at screening</h2><p>{screening.patient_snapshot.date_of_birth ? `Born ${screening.patient_snapshot.date_of_birth}` : 'Date of birth not recorded'}{screening.patient_snapshot.sex ? ` · ${screening.patient_snapshot.sex}` : ''}</p></div><div className="snapshot-facts">{screening.patient_snapshot.facts.length ? screening.patient_snapshot.facts.slice(0, 6).map((fact) => <span key={fact.id}><strong>{fact.concept}</strong>{fact.value_numeric ?? fact.value_text ?? fact.assertion} {fact.unit}</span>) : <span>No additional structured facts in this snapshot.</span>}</div></section>
    <ResearchToolsPanel screening={screening} token={token} />
    <div className="screening-split"><section className="criteria-section"><div className="section-heading"><div><p className="eyebrow">Screening evidence</p><h2>Criteria</h2><p>Unknown criteria appear first.</p></div></div>{ordered.map((item) => <article className={`evaluation evaluation-${item.result}`} id={`criterion-${item.id}`} key={item.id} tabIndex={-1}><div className="evaluation-head"><span className="criterion-order">{item.criterion_order}</span><div><span className="record-kind">{item.criterion_kind}</span><h3>{item.criterion_source_text}</h3></div><span className={`state state-${item.result}`}>{item.result}</span></div><p className="canonical">{item.canonical_explanation}</p><div className="evidence-grid"><div><strong>Assessment</strong><p>{reasonLabel(item.reason_code)}</p></div><div><strong>{isConfigurationReason(item.reason_code) ? 'Configuration action' : 'Recorded evidence'}</strong>{isConfigurationReason(item.reason_code) ? <p>Ask the trial author to correct this criterion in a draft protocol, approve the new version, and run a new screening.</p> : item.evidence.length ? <ul>{item.evidence.map((evidence, index) => <li key={`${evidence.fact_id}-${index}`}>{evidenceValue(evidence)}<small>{evidence.source_label}</small></li>)}</ul> : <p>No supporting value was recorded.</p>}</div>{item.missing_information.length > 0 && <div><strong>Needed to resolve</strong><ul>{item.missing_information.map((missing, index) => <li key={`${missing.fact}-${index}`}>{missing.detail || 'Additional recorded information is required.'}</li>)}</ul></div>}</div><details className="audit-details"><summary>How this result is reproduced</summary><p>It uses the saved patient snapshot and trial protocol shown above.</p></details><a className="citation-return" href="#screening-chat-panel">Back to the result assistant</a></article>)}</section><aside className="screening-chat"><ScreeningChatPanel screeningId={screening.id} /></aside></div>
    <footer className="result-metadata">Screened {screening.screening_date} · Engine {screening.engine_version} · DSL {screening.dsl_version}</footer>
  </section>
}
