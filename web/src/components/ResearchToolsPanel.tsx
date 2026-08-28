import { Activity, Network, UsersRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  apiRequest,
  type RiskContext,
  type RiskPrediction,
  type Screening,
} from '../api/client'

export function ResearchToolsPanel({ screening, token }: { screening: Screening; token: string | null }) {
  const [dropoutStatus, setDropoutStatus] = useState(
    screening.overall_state === 'potentially_eligible' ? 'Checking follow-up…' : 'Not available',
  )

  useEffect(() => {
    if (screening.overall_state !== 'potentially_eligible') return
    let active = true
    const load = async () => {
      try {
        const context = await apiRequest<RiskContext>(`/research/risk/screenings/${screening.id}/context`, {}, token)
        if (!active) return
        if (context.status === 'unsupported_model_input') {
          setDropoutStatus('Not supported for this condition')
          return
        }
        if (context.status === 'unlinked') {
          setDropoutStatus('Not started')
          return
        }
        if (context.status === 'incomplete' || !context.follow_up) {
          setDropoutStatus('Information needed')
          return
        }
        const predictions = await apiRequest<RiskPrediction[]>(`/research/risk/predictions?screening_id=${screening.id}&limit=10`, {}, token)
        if (!active) return
        const prediction = predictions.find((item) => item.follow_up_snapshot_id === context.follow_up?.id)
        setDropoutStatus(prediction ? `Estimate available · ${(prediction.probability * 100).toFixed(1)}%` : 'Ready to predict')
      } catch {
        if (active) setDropoutStatus('Status unavailable')
      }
    }
    void load()
    return () => { active = false }
  }, [screening.id, screening.overall_state, token])

  return <section className="research-tools research-tools-compact" aria-labelledby="research-tools-title">
    <div className="research-heading"><h2 id="research-tools-title">Research</h2></div>
    <div className="research-tool-actions">
      {screening.overall_state === 'potentially_eligible' ? <Link className="research-action" to={`/screenings/${screening.id}/dropout`}>
        <Activity aria-hidden="true" size={19} />
        <span><strong>Dropout follow-up</strong><small>{dropoutStatus}</small></span>
      </Link> : <span className="research-action disabled" aria-disabled="true">
        <Activity aria-hidden="true" size={19} />
        <span><strong>Dropout follow-up</strong><small>{dropoutStatus}</small></span>
      </span>}
      <Link className="research-action" to={`/research/cohorts?screening=${screening.id}&representation=patient_fact&tool=cohort`}>
        <Network aria-hidden="true" size={19} />
        <span><strong>Cohort context</strong><small>Open in Cohort Atlas</small></span>
      </Link>
      <Link className="research-action" to={`/research/cohorts?screening=${screening.id}&representation=patient_fact&tool=similarity`}>
        <UsersRound aria-hidden="true" size={19} />
        <span><strong>Similar participants</strong><small>Compare in Cohort Atlas</small></span>
      </Link>
    </div>
  </section>
}
