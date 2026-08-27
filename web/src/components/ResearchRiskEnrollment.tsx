import type { FormEvent } from 'react'

import type { ResearchEnrollment, Screening } from '../api/client'
import { baselineFields, displayFeatureValue, featureLabels, numeric } from './researchRiskPresentation'

export function EnrollmentSetup({
  screening,
  busy,
  onSubmit,
}: {
  screening: Screening
  busy: boolean
  onSubmit: (payload: unknown) => Promise<void>
}) {
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const baseline = Object.fromEntries(baselineFields.map((field) => [field.name, {
      value: field.kind === 'number' ? numeric(data.get(field.name)) : String(data.get(field.name)),
      source: 'Research follow-up intake',
    }]))
    await onSubmit({ enrollment_date: String(data.get('enrollment_date')), baseline })
  }

  return (
    <section className="risk-stage-panel enrollment-setup" aria-labelledby="baseline-setup-title">
      <div className="immutable-prefill">
        <div><h4>{screening.patient_snapshot.display_name}</h4><p>{screening.trial_version.title}</p></div>
        <span>{screening.patient_snapshot.facts.filter((fact) => fact.assertion === 'present' && fact.fact_type === 'condition').length} conditions<br />{screening.patient_snapshot.facts.filter((fact) => fact.assertion === 'present' && fact.fact_type === 'medication').length} medications</span>
      </div>
      <form className="research-form" onSubmit={(event) => { void submit(event) }}>
        <div className="form-section-head"><h4 id="baseline-setup-title">Complete baseline setup</h4><span>Day 0</span></div>
        <div className="research-form-grid">
          <label>Enrollment date<input name="enrollment_date" type="date" min={screening.screening_date} defaultValue={screening.screening_date} required /></label>
          {baselineFields.map((field) => <label key={field.name}>{field.label}{field.kind === 'select' ? <select name={field.name} required defaultValue=""><option value="" disabled>Select…</option>{field.options?.map((option) => <option key={option} value={option}>{option.replaceAll('_', ' ')}</option>)}</select> : <input name={field.name} type="number" min={field.min} max={field.max} step={field.step} required />} {'hint' in field ? <small>{field.hint}</small> : null}</label>)}
        </div>
        <p className="source-line">All seven fields are required. Missing values are never replaced with zero.</p>
        <button className="primary-button" type="submit" disabled={busy}>{busy ? 'Starting follow-up…' : 'Start follow-up'}</button>
      </form>
    </section>
  )
}

export function BaselineSummary({ enrollment }: { enrollment: ResearchEnrollment }) {
  const visible = enrollment.baseline.filter((feature) => !feature.missing)
  return (
    <details className="baseline-summary">
      <summary><span><strong>Baseline recorded</strong><small>{enrollment.enrollment_date}</small></span><span>{visible.length} details</span></summary>
      <div className="baseline-summary-grid">
        {visible.map((feature) => <div key={feature.name}><span>{featureLabels[feature.name] ?? feature.name.replaceAll('_', ' ')}</span><strong>{displayFeatureValue(feature.value)}</strong></div>)}
      </div>
    </details>
  )
}
