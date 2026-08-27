import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiRequest, type Screening } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ResearchRiskPanel } from '../components/ResearchRiskPanel'
import { stateLabel } from './screeningHelpers'

export function DropoutWorkflowPage() {
  const { screeningId = '' } = useParams()
  const { token } = useAuth()
  const [screening, setScreening] = useState<Screening | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      setScreening(await apiRequest(`/screenings/${screeningId}`, {}, token))
      setError('')
    } catch {
      setError('This screening could not be loaded.')
    }
  }, [screeningId, token])

  useEffect(() => { void load() }, [load])

  if (error) return <div className="form-error" role="alert">{error}</div>
  if (!screening) return <div className="loading-state">Loading dropout follow-up…</div>
  if (!screening.patient_snapshot || !screening.trial_version) {
    return <div className="form-error" role="alert">This screening is missing its patient or trial details.</div>
  }

  return <section className="route-entry workspace-page">
    <Link className="back-link" to={`/screenings/${screening.id}`}>← Screening result</Link>
    <header className="page-heading dropout-workflow-heading">
      <div><h1>Dropout follow-up</h1><p>{screening.patient_snapshot.display_name} · {screening.trial_version.title}</p></div>
      <span className={`state state-${screening.overall_state}`}>{stateLabel(screening.overall_state)}</span>
    </header>
    {screening.overall_state === 'potentially_eligible'
      ? <ResearchRiskPanel screening={screening} token={token} />
      : <div className="empty-state"><h2>Dropout follow-up is not available</h2><p>This workflow begins from a potentially eligible screening.</p></div>}
  </section>
}
