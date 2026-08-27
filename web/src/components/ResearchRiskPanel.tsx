import { useCallback, useEffect, useState } from 'react'

import {
  ApiError,
  apiRequest,
  type Day30Summary,
  type ResearchFollowUp,
  type RiskContext,
  type RiskPrediction,
  type RiskScenarioResponse,
  type Screening,
} from '../api/client'
import { BaselineSummary, EnrollmentSetup } from './ResearchRiskEnrollment'
import { Day30SummaryForm } from './ResearchRiskFollowUp'
import { PredictionStage } from './ResearchRiskPrediction'

function requestMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback
}

export function ResearchRiskPanel({ screening, token }: { screening: Screening; token: string | null }) {
  const [context, setContext] = useState<RiskContext | null>(null)
  const [prediction, setPrediction] = useState<RiskPrediction | null>(null)
  const [scenarios, setScenarios] = useState<RiskScenarioResponse | null>(null)
  const [editing, setEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const next = await apiRequest<RiskContext>(`/research/risk/screenings/${screening.id}/context`, {}, token)
      setContext(next)
      if (!next.follow_up?.input_summary) {
        setPrediction(null)
        setScenarios(null)
        return
      }
      const predictions = await apiRequest<RiskPrediction[]>(`/research/risk/predictions?screening_id=${screening.id}&limit=10`, {}, token)
      const current = predictions.find((item) => item.follow_up_snapshot_id === next.follow_up?.id) ?? null
      setPrediction(current)
      setScenarios(current ? await apiRequest<RiskScenarioResponse>('/research/risk/scenarios', {
        method: 'POST',
        body: JSON.stringify({ follow_up_snapshot_id: next.follow_up.id }),
      }, token) : null)
    } catch (caught) {
      setError(requestMessage(caught, 'The dropout estimate could not be loaded.'))
    } finally {
      setLoading(false)
    }
  }, [screening.id, token])

  useEffect(() => { void load() }, [load])

  const saveSummary = async (summary: Day30Summary) => {
    if (!context?.enrollment) return
    setBusy(true)
    setError('')
    try {
      const followUp = await apiRequest<ResearchFollowUp>(`/research/enrollments/${context.enrollment.id}/day30-summary`, {
        method: 'POST',
        body: JSON.stringify(summary),
      }, token)
      const [nextPrediction, nextScenarios] = await Promise.all([
        apiRequest<RiskPrediction>('/research/risk/predictions', {
          method: 'POST',
          body: JSON.stringify({ follow_up_snapshot_id: followUp.id }),
        }, token),
        apiRequest<RiskScenarioResponse>('/research/risk/scenarios', {
          method: 'POST',
          body: JSON.stringify({ follow_up_snapshot_id: followUp.id }),
        }, token),
      ])
      setContext((current) => current ? { ...current, status: 'ready', follow_up: followUp } : current)
      setPrediction(nextPrediction)
      setScenarios(nextScenarios)
      setEditing(false)
    } catch (caught) {
      setError(requestMessage(caught, 'The estimate could not be calculated.'))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <div className="research-detail-panel"><div className="research-loading">Loading dropout estimate…</div></div>
  if (!context) return <div className="research-detail-panel"><div className="form-error" role="alert">{error || 'The dropout estimate is unavailable.'}</div></div>

  return <div className="research-detail-panel risk-workspace">
    {error ? <div className="form-error" role="alert">{error}</div> : null}
    {context.status === 'unlinked' ? <EnrollmentSetup screening={screening} busy={busy} onSubmit={async (payload) => {
      setBusy(true)
      setError('')
      try {
        await apiRequest(`/research/screenings/${screening.id}/enrollment`, { method: 'POST', body: JSON.stringify(payload) }, token)
        await load()
      } catch (caught) {
        setError(requestMessage(caught, 'Baseline setup could not be saved.'))
      } finally {
        setBusy(false)
      }
    }} /> : context.enrollment ? <>
      <BaselineSummary enrollment={context.enrollment} />
      {!context.follow_up?.input_summary || editing ? <Day30SummaryForm summary={context.follow_up?.input_summary ?? null} busy={busy} onSubmit={saveSummary} onCancel={context.follow_up?.input_summary ? () => setEditing(false) : undefined} /> : prediction ? <PredictionStage followUp={context.follow_up} prediction={prediction} scenarios={scenarios} onEdit={() => setEditing(true)} /> : <Day30SummaryForm summary={context.follow_up.input_summary} busy={busy} onSubmit={saveSummary} />}
    </> : null}
  </div>
}
