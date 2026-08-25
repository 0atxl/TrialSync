import { type CSSProperties, type FormEvent, type ReactNode, useCallback, useEffect, useState } from 'react'

import {
  ApiError,
  apiRequest,
  type ResearchEnrollment,
  type ResearchFollowUp,
  type RiskContext,
  type RiskPrediction,
  type Screening,
} from '../api/client'

const baselineFields = [
  { name: 'site_region', label: 'Site region', kind: 'select', options: ['central', 'north', 'south', 'east', 'west'] },
  { name: 'treatment_arm', label: 'Treatment arm', kind: 'select', options: ['active', 'control'] },
  { name: 'baseline_functional_severity', label: 'Baseline functional severity', kind: 'number', min: 0, max: 1, step: 0.01, hint: '0–1 recorded score' },
  { name: 'patient_reported_burden', label: 'Patient-reported burden', kind: 'number', min: 0, max: 1, step: 0.01, hint: '0–1 recorded score' },
  { name: 'baseline_treatment_burden', label: 'Baseline treatment burden', kind: 'number', min: 0, max: 20, step: 1, hint: '0–20 scale' },
  { name: 'travel_access_burden', label: 'Travel/access burden', kind: 'number', min: 0, max: 4, step: 1, hint: '0–4 scale' },
  { name: 'support_availability', label: 'Support availability', kind: 'number', min: 0, max: 4, step: 1, hint: '0–4 scale' },
] as const

const featureLabels: Record<string, string> = {
  condition_category: 'Condition category', site_region: 'Site region', treatment_arm: 'Treatment arm',
  age: 'Age at screening', sex: 'Recorded sex', baseline_functional_severity: 'Baseline functional severity',
  patient_reported_burden: 'Patient-reported burden', baseline_comorbidity_burden: 'Recorded condition burden',
  baseline_treatment_burden: 'Baseline treatment burden', travel_access_burden: 'Travel/access burden',
  support_availability: 'Support availability', medication_count: 'Recorded medication count',
  latest_functional_severity: 'Latest functional severity', functional_severity_slope: 'Functional severity slope',
  functional_observation_count: 'Functional observations', missed_dose_rate: 'Missed-dose rate',
  delayed_visit_count: 'Delayed visits', missed_visit_rate: 'Missed-visit rate',
  mean_visit_delay_days: 'Mean visit delay', measurement_missingness_rate: 'Measurement missingness',
  adverse_event_count: 'Adverse-event count', adverse_event_burden: 'Adverse-event burden',
}

type EventCounts = { dose_events: number; visit_events: number; measurements: number; adverse_events: number }
const emptyCounts: EventCounts = { dose_events: 0, visit_events: 0, measurements: 0, adverse_events: 0 }

function message(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback
}

function addDays(value: string, days: number) {
  const date = new Date(`${value}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

function numeric(value: FormDataEntryValue | null) {
  return Number(String(value ?? ''))
}

function displayValue(value: string | number | null) {
  if (value == null) return 'Missing'
  if (typeof value === 'number' && !Number.isInteger(value)) return value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
  return String(value).replaceAll('_', ' ')
}

export function ResearchRiskPanel({ screening, token }: { screening: Screening; token: string | null }) {
  const [context, setContext] = useState<RiskContext | null>(null)
  const [prediction, setPrediction] = useState<RiskPrediction | null>(null)
  const [events, setEvents] = useState<EventCounts>(emptyCounts)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [snapshotStale, setSnapshotStale] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const next = await apiRequest<RiskContext>(`/research/risk/screenings/${screening.id}/context`, {}, token)
      setContext(next)
      if (next.enrollment) {
        const [eventResponse, predictions] = await Promise.all([
          apiRequest<Record<keyof EventCounts, unknown[]>>(`/research/enrollments/${next.enrollment.id}/events`, {}, token),
          apiRequest<RiskPrediction[]>(`/research/risk/predictions?screening_id=${screening.id}&limit=1`, {}, token),
        ])
        setEvents({
          dose_events: eventResponse.dose_events.filter((item) => !(item as { is_superseded?: boolean }).is_superseded).length,
          visit_events: eventResponse.visit_events.filter((item) => !(item as { is_superseded?: boolean }).is_superseded).length,
          measurements: eventResponse.measurements.filter((item) => !(item as { is_superseded?: boolean }).is_superseded).length,
          adverse_events: eventResponse.adverse_events.filter((item) => !(item as { is_superseded?: boolean }).is_superseded).length,
        })
        setPrediction(predictions[0] ?? null)
      }
    } catch (caught) {
      setError(message(caught, 'The dropout-risk workspace could not be loaded.'))
    } finally {
      setLoading(false)
    }
  }, [screening.id, token])

  useEffect(() => { void load() }, [load])

  const mutate = async (label: string, action: () => Promise<unknown>, success: string, reload = true) => {
    setBusy(label); setError(''); setNotice('')
    try {
      await action()
      setNotice(success)
      if (reload) await load()
      return true
    } catch (caught) {
      setError(message(caught, 'The research record could not be updated.'))
      return false
    } finally {
      setBusy('')
    }
  }

  if (loading) return <div className="research-detail-panel"><div className="research-loading">Loading linked enrollment and follow-up status…</div></div>
  if (!context) return <div className="research-detail-panel"><div className="form-error" role="alert">{error || 'The dropout-risk workspace is unavailable.'}</div></div>

  return <div className="research-detail-panel risk-workspace">
    <div className="research-detail-head"><div><p className="eyebrow">Research retention signal</p><h3>Day-30 dropout-risk workspace</h3></div><span className={`readiness readiness-${context.status}`}>{context.status === 'unlinked' ? 'Follow-up not started' : context.status === 'ready' && !snapshotStale ? 'Ready to predict' : 'Day-30 information needed'}</span></div>
    <div className="research-boundary risk-boundary"><strong>Eligibility remains {screening.overall_state.replaceAll('_', ' ')}.</strong> This separate generated-data model estimates dropout from day 30 through day 90 and cannot change that result.</div>
    {error && <div className="form-error" role="alert">{error}</div>}
    {notice && <div className="research-notice" role="status">{notice}</div>}
    <ModelStrip context={context} />
    {context.status === 'unlinked' ? <EnrollmentSetup screening={screening} busy={busy} onSubmit={async (payload) => {
      await mutate('enrollment', () => apiRequest(`/research/screenings/${screening.id}/enrollment`, { method: 'POST', body: JSON.stringify(payload) }, token), 'Research follow-up started with immutable baseline linkage.')
    }} /> : context.enrollment && <>
      <BaselineSummary enrollment={context.enrollment} />
      <Day30Events enrollment={context.enrollment} events={events} busy={busy} onEvent={async (route, payload, eventLabel) => {
        const success = await mutate(route, () => apiRequest(`/research/enrollments/${context.enrollment!.id}/${route}`, { method: 'POST', body: JSON.stringify(payload) }, token), `${eventLabel} recorded. Rebuild the day-30 snapshot before prediction.`)
        if (success) setSnapshotStale(true)
      }} />
      <SnapshotReadiness followUp={context.follow_up} stale={snapshotStale} busy={busy} onBuild={async (confirmations) => {
        const success = await mutate('snapshot', async () => {
          const snapshot = await apiRequest<ResearchFollowUp>(`/research/enrollments/${context.enrollment!.id}/follow-up-snapshots`, { method: 'POST', body: JSON.stringify(confirmations) }, token)
          setContext((current) => current ? { ...current, status: snapshot.status === 'ready' ? 'ready' : 'incomplete', follow_up: snapshot } : current)
        }, 'Day-30 snapshot rebuilt. Missing fields remain explicit.', false)
        if (success) setSnapshotStale(false)
      }} />
      {context.follow_up?.status === 'ready' && !snapshotStale && <PredictionAction followUp={context.follow_up} prediction={prediction} busy={busy} onPredict={async () => {
        setBusy('prediction'); setError(''); setNotice('')
        try {
          const result = await apiRequest<RiskPrediction>('/research/risk/predictions', { method: 'POST', body: JSON.stringify({ follow_up_snapshot_id: context.follow_up!.id }) }, token)
          setPrediction(result)
          setNotice('Prediction saved. The deterministic eligibility evidence is unchanged.')
        } catch (caught) { setError(message(caught, 'The risk prediction could not be created.')) }
        finally { setBusy('') }
      }} />}
    </>}
  </div>
}

function ModelStrip({ context }: { context: RiskContext }) {
  const model = context.model
  return <div className="model-strip">
    <div><span>Runtime model</span><strong>XGBoost · {model.candidate_id}</strong></div><div><span>Observation</span><strong>Through day 30</strong></div><div><span>Horizon</span><strong>Day {model.horizon_day}</strong></div><div><span>Threshold</span><strong>{model.threshold.toFixed(3)}</strong></div>
    {model.artifact_status === 'degraded' && <p role="alert">Model artifact unavailable: {model.artifact_message}</p>}
  </div>
}

function EnrollmentSetup({ screening, busy, onSubmit }: { screening: Screening; busy: string; onSubmit: (payload: unknown) => Promise<void> }) {
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const baseline = Object.fromEntries(baselineFields.map((field) => [field.name, {
      value: field.kind === 'number' ? numeric(data.get(field.name)) : String(data.get(field.name)),
      source: 'Research follow-up intake',
    }]))
    await onSubmit({ enrollment_date: String(data.get('enrollment_date')), baseline })
  }
  return <div className="enrollment-setup">
    <div className="immutable-prefill"><div><p className="eyebrow">Immutable prefill</p><h4>{screening.patient_snapshot.display_name}</h4><p>{screening.patient_snapshot.date_of_birth ? `Date of birth ${screening.patient_snapshot.date_of_birth}` : 'Date of birth missing'} · {screening.patient_snapshot.sex ?? 'Sex not recorded'} · {screening.trial_version.title}</p></div><span>{screening.patient_snapshot.facts.filter((fact) => fact.assertion === 'present' && fact.fact_type === 'condition').length} conditions<br />{screening.patient_snapshot.facts.filter((fact) => fact.assertion === 'present' && fact.fact_type === 'medication').length} medications</span></div>
    <form className="research-form" onSubmit={(event) => { void submit(event) }}>
      <div className="form-section-head"><div><h4>Start research follow-up</h4><p>Screening-owned values above are resolved by the server. Record the seven enrollment-only baseline values once.</p></div><span>Day 0</span></div>
      <div className="research-form-grid"><label>Enrollment date<input name="enrollment_date" type="date" min={screening.screening_date} defaultValue={screening.screening_date} required /></label>{baselineFields.map((field) => <label key={field.name}>{field.label}{field.kind === 'select' ? <select name={field.name} required defaultValue=""><option value="" disabled>Select…</option>{field.options?.map((option) => <option key={option} value={option}>{option.replaceAll('_', ' ')}</option>)}</select> : <input name={field.name} type="number" min={field.min} max={field.max} step={field.step} required />} {'hint' in field && <small>{field.hint}</small>}</label>)}</div>
      <p className="source-line">Source for entered values: <strong>Research follow-up intake</strong>. Missing fields are rejected rather than replaced with zero.</p>
      <button className="primary-button" type="submit" disabled={busy === 'enrollment'}>{busy === 'enrollment' ? 'Starting follow-up…' : 'Start research follow-up'}</button>
    </form>
  </div>
}

function BaselineSummary({ enrollment }: { enrollment: ResearchEnrollment }) {
  return <details className="baseline-summary"><summary><span><strong>Linked baseline context</strong><small>{enrollment.baseline.length - enrollment.missing_baseline_features.length} of {enrollment.baseline.length} model baseline fields resolved</small></span><span>Enrollment {enrollment.enrollment_date}</span></summary><div className="feature-ledger">{enrollment.baseline.map((feature) => <div key={feature.name} className={feature.missing ? 'missing' : ''}><span>{featureLabels[feature.name] ?? feature.name}</span><strong>{displayValue(feature.value)}</strong><small>{feature.source ?? 'Source required'}</small></div>)}</div></details>
}

function Day30Events({ enrollment, events, busy, onEvent }: { enrollment: ResearchEnrollment; events: EventCounts; busy: string; onEvent: (route: string, payload: Record<string, unknown>, label: string) => Promise<void> }) {
  const minDate = enrollment.enrollment_date
  const maxDate = addDays(minDate, enrollment.observation_cutoff_day)
  return <section className="event-capture"><div className="form-section-head"><div><p className="eyebrow">Observed through day 30</p><h4>Follow-up records</h4><p>Enter observable events. TrialSync derives rates and counts; an empty record never becomes an observed zero.</p></div><span>{minDate} → {maxDate}</span></div><div className="event-grid">
    <EventForm title="Doses" count={events.dose_events} summary="Scheduled and administered counts" busy={busy === 'dose-events'} onSubmit={async (data) => {
      const scheduled = numeric(data.get('scheduled_count')); const administered = numeric(data.get('administered_count'))
      await onEvent('dose-events', { source_label: 'Day-30 dose log', medication_concept: String(data.get('medication_concept')), scheduled_date: String(data.get('scheduled_date')), scheduled_count: scheduled, administered_count: administered, status: administered === scheduled ? 'administered' : administered === 0 ? 'missed' : 'partially_administered' }, 'Dose event')
    }}><label>Medication or study treatment<input name="medication_concept" defaultValue="study_treatment" required /></label><div className="paired-fields"><label>Scheduled<input name="scheduled_count" type="number" min="1" max="1000" defaultValue="1" required /></label><label>Administered<input name="administered_count" type="number" min="0" max="1000" defaultValue="1" required /></label></div><label>Scheduled date<input name="scheduled_date" type="date" min={minDate} max={maxDate} defaultValue={maxDate} required /></label></EventForm>
    <EventForm title="Visits" count={events.visit_events} summary="Completed, delayed, or missed visits" busy={busy === 'visit-events'} onSubmit={async (data) => {
      const status = String(data.get('status')); const scheduled = String(data.get('scheduled_date')); const completed = String(data.get('completed_date') ?? '')
      await onEvent('visit-events', { source_label: 'Day-30 visit log', visit_type: String(data.get('visit_type')), scheduled_date: scheduled, completed_date: status === 'missed' ? null : completed, status: status === 'completed' && completed > scheduled ? 'delayed' : status }, 'Visit event')
    }}><label>Visit type<input name="visit_type" defaultValue="follow_up" required /></label><label>Status<select name="status" defaultValue="completed"><option value="completed">Completed</option><option value="missed">Missed</option></select></label><div className="paired-fields"><label>Scheduled<input name="scheduled_date" type="date" min={minDate} max={maxDate} defaultValue={maxDate} required /></label><label>Completed date<input name="completed_date" type="date" min={minDate} max={maxDate} defaultValue={maxDate} /></label></div></EventForm>
    <EventForm title="Functional measurements" count={events.measurements} summary="Observed or explicitly missed assessments" busy={busy === 'measurements'} onSubmit={async (data) => {
      const observed = data.get('observed') === 'on'
      await onEvent('measurements', { source_label: 'Day-30 functional assessment', concept: 'functional_severity', value_numeric: observed ? numeric(data.get('value_numeric')) : null, unit: observed ? 'score' : null, observed, observed_date: String(data.get('observed_date')) }, observed ? 'Functional measurement' : 'Missing functional assessment')
    }}><label className="check-row"><input name="observed" type="checkbox" defaultChecked />Assessment was observed</label><label>Functional severity score<input name="value_numeric" type="number" min="0" max="1" step="0.01" defaultValue="0.5" /></label><label>Assessment date<input name="observed_date" type="date" min={addDays(minDate, 1)} max={maxDate} defaultValue={maxDate} required /></label></EventForm>
    <EventForm title="Adverse events" count={events.adverse_events} summary="Recorded event grade and status" busy={busy === 'adverse-events'} onSubmit={async (data) => {
      await onEvent('adverse-events', { source_label: 'Day-30 safety review', event_concept: String(data.get('event_concept')), onset_date: String(data.get('onset_date')), severity_grade: numeric(data.get('severity_grade')), serious: data.get('serious') === 'on', relatedness: String(data.get('relatedness')), outcome: 'ongoing' }, 'Adverse event')
    }}><label>Event term<input name="event_concept" placeholder="e.g. nausea" required /></label><div className="paired-fields"><label>Grade<select name="severity_grade" defaultValue="1"><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select></label><label>Relatedness<select name="relatedness" defaultValue="unknown"><option value="unknown">Unknown</option><option value="unrelated">Unrelated</option><option value="unlikely">Unlikely</option><option value="possible">Possible</option><option value="probable">Probable</option><option value="definite">Definite</option></select></label></div><label>Onset date<input name="onset_date" type="date" min={minDate} max={maxDate} defaultValue={maxDate} required /></label><label className="check-row"><input name="serious" type="checkbox" />Serious event</label></EventForm>
  </div></section>
}

function EventForm({ title, count, summary, busy, onSubmit, children }: { title: string; count: number; summary: string; busy: boolean; onSubmit: (data: FormData) => Promise<void>; children: ReactNode }) {
  const submit = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); await onSubmit(new FormData(event.currentTarget)) }
  return <details className="event-form"><summary><span><strong>{title}</strong><small>{summary}</small></span><span>{count} recorded</span></summary><form onSubmit={(event) => { void submit(event) }}>{children}<button className="secondary-button" type="submit" disabled={busy}>{busy ? 'Recording…' : `Add ${title.toLowerCase()} record`}</button></form></details>
}

function SnapshotReadiness({ followUp, stale, busy, onBuild }: { followUp: ResearchFollowUp | null; stale: boolean; busy: string; onBuild: (value: Record<string, boolean>) => Promise<void> }) {
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    await onBuild({ dose_record_complete: data.get('dose') === 'on', visit_record_complete: data.get('visit') === 'on', measurement_record_complete: data.get('measurement') === 'on', adverse_event_record_complete: data.get('adverse') === 'on' })
  }
  return <section className="snapshot-readiness"><div><p className="eyebrow">Day-30 snapshot</p><h4>{stale ? 'New events need a new snapshot' : followUp?.status === 'ready' ? 'All 22 features resolved' : 'Confirm reviewed record groups'}</h4><p>Confirmation means the record was reviewed through day 30. It does not insert a numeric value.</p></div><form onSubmit={(event) => { void submit(event) }}><div className="confirmation-grid"><label><input name="dose" type="checkbox" />Dose record complete</label><label><input name="visit" type="checkbox" />Visit record complete</label><label><input name="measurement" type="checkbox" />Measurement record complete</label><label><input name="adverse" type="checkbox" />Safety record complete, including no events if empty</label></div><button className="primary-button" type="submit" disabled={busy === 'snapshot'}>{busy === 'snapshot' ? 'Building snapshot…' : 'Build day-30 snapshot'}</button></form>
    {followUp && <div className={followUp.status === 'ready' && !stale ? 'snapshot-status ready' : 'snapshot-status incomplete'}><strong>{followUp.status === 'ready' && !stale ? 'Ready' : `${followUp.missing_features.length} features unresolved`}</strong>{followUp.missing_features.length > 0 && <span>{followUp.missing_features.map((name) => featureLabels[name] ?? name).join(' · ')}</span>}</div>}
  </section>
}

function PredictionAction({ followUp, prediction, busy, onPredict }: { followUp: ResearchFollowUp; prediction: RiskPrediction | null; busy: string; onPredict: () => Promise<void> }) {
  return <section className="prediction-region">
    <div className="prediction-action"><div><p className="eyebrow">Ready feature snapshot</p><h4>Predict dropout risk</h4><p>Uses the immutable day-{followUp.cutoff_day} feature snapshot shown above.</p></div><button className="primary-button" type="button" disabled={busy === 'prediction'} onClick={() => { void onPredict() }}>{busy === 'prediction' ? 'Running XGBoost…' : prediction ? 'Reopen saved prediction' : 'Predict dropout risk'}</button></div>
    {prediction && <PredictionResult prediction={prediction} />}
  </section>
}

function PredictionResult({ prediction }: { prediction: RiskPrediction }) {
  const probability = prediction.probability * 100
  const threshold = prediction.threshold * 100
  return <div className="prediction-result">
    <div className="risk-gauge" style={{ '--risk-probability': `${probability}%`, '--risk-threshold': `${threshold}%` } as CSSProperties}><div><span style={{ left: `${Math.min(100, threshold)}%` }} /></div><strong>{probability.toFixed(1)}%</strong><small>estimated dropout probability by day {prediction.horizon_day}</small><p>Stored threshold {threshold.toFixed(1)}% · <b>{prediction.research_label.replaceAll('_', ' ')}</b></p></div>
    <div className="contribution-panel"><div><p className="eyebrow">XGBoost contributions</p><h4>What moved this model output</h4></div><ol>{prediction.top_contributions.map((item) => <li key={item.feature}><span><strong>{featureLabels[item.feature] ?? item.feature.replaceAll('_', ' ')}</strong><small>Observed value {displayValue(item.value)}</small></span><span className={`contribution-${item.direction}`}>{item.shap_value > 0 ? '+' : ''}{item.shap_value.toFixed(3)}<small>{item.direction} output</small></span></li>)}</ol><p>SHAP describes this model’s calculation; it does not establish a cause.</p></div>
    <dl className="research-metadata"><div><dt>Model</dt><dd>XGBoost · {prediction.model.candidate_id}</dd></div><div><dt>Version</dt><dd>{prediction.model.name}:{prediction.model.version}</dd></div><div><dt>Observation cutoff</dt><dd>Day {prediction.observation_cutoff_day}</dd></div><div><dt>Prediction horizon</dt><dd>Day {prediction.horizon_day}</dd></div></dl>
    <p className="research-boundary">Research prediction over generated training data only; not a clinical or eligibility decision.</p>
  </div>
}
