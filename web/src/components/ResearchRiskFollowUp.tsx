import { useState, type FormEvent } from 'react'

import type { Day30Summary } from '../api/client'

type Draft = Record<keyof Day30Summary, string>

const fields: Array<{
  name: keyof Day30Summary
  label: string
  min: number
  max: number
  step?: number
}> = [
  { name: 'scheduled_doses', label: 'Doses expected', min: 1, max: 100 },
  { name: 'missed_doses', label: 'Doses missed', min: 0, max: 100 },
  { name: 'longest_missed_dose_streak', label: 'Longest missed-dose run', min: 0, max: 30 },
  { name: 'scheduled_visits', label: 'Visits expected', min: 1, max: 100 },
  { name: 'missed_visits', label: 'Visits missed', min: 0, max: 50 },
  { name: 'longest_missed_visit_streak', label: 'Longest missed-visit run', min: 0, max: 15 },
  { name: 'delayed_visits', label: 'Visits delayed', min: 0, max: 100 },
  { name: 'total_visit_delay_days', label: 'Total delay days', min: 0, max: 3000 },
  { name: 'expected_assessments', label: 'Assessments expected', min: 1, max: 100 },
  { name: 'completed_assessments', label: 'Assessments completed', min: 1, max: 100 },
  { name: 'latest_functional_severity', label: 'Latest severity score', min: 0, max: 1, step: 0.01 },
  { name: 'latest_assessment_day', label: 'Latest assessment day', min: 1, max: 30 },
  { name: 'adverse_event_count', label: 'Adverse events', min: 0, max: 100 },
  { name: 'adverse_event_burden', label: 'Sum of severity grades', min: 0, max: 400 },
]

const groups = [
  { title: 'Doses', names: ['scheduled_doses', 'missed_doses', 'longest_missed_dose_streak'] },
  { title: 'Visits', names: ['scheduled_visits', 'missed_visits', 'longest_missed_visit_streak', 'delayed_visits', 'total_visit_delay_days'] },
  { title: 'Assessment', names: ['expected_assessments', 'completed_assessments', 'latest_functional_severity', 'latest_assessment_day'] },
  { title: 'Safety', names: ['adverse_event_count', 'adverse_event_burden'] },
] as const

function initialDraft(summary: Day30Summary | null): Draft {
  return Object.fromEntries(fields.map(({ name }) => [name, summary ? String(summary[name]) : ''])) as Draft
}

function value(draft: Draft, name: keyof Day30Summary) {
  return Number(draft[name])
}

function validate(draft: Draft) {
  if (fields.some(({ name }) => draft[name].trim() === '')) return 'Complete every field. Enter 0 when none occurred.'
  if (value(draft, 'missed_doses') > value(draft, 'scheduled_doses')) return 'Missed doses cannot exceed expected doses.'
  if (value(draft, 'missed_doses') === 0 && value(draft, 'longest_missed_dose_streak') !== 0) return 'Enter 0 for the longest missed-dose run when no doses were missed.'
  if (value(draft, 'missed_doses') > 0 && (value(draft, 'longest_missed_dose_streak') < 1 || value(draft, 'longest_missed_dose_streak') > value(draft, 'missed_doses'))) return 'The longest missed-dose run must be between 1 and the number of missed doses.'
  if (value(draft, 'missed_visits') > value(draft, 'scheduled_visits')) return 'Missed visits cannot exceed expected visits.'
  if (value(draft, 'missed_visits') === 0 && value(draft, 'longest_missed_visit_streak') !== 0) return 'Enter 0 for the longest missed-visit run when no visits were missed.'
  if (value(draft, 'missed_visits') > 0 && (value(draft, 'longest_missed_visit_streak') < 1 || value(draft, 'longest_missed_visit_streak') > value(draft, 'missed_visits'))) return 'The longest missed-visit run must be between 1 and the number of missed visits.'
  if (value(draft, 'delayed_visits') > value(draft, 'scheduled_visits') - value(draft, 'missed_visits')) return 'Delayed visits cannot exceed completed visits.'
  if (value(draft, 'delayed_visits') === 0 && value(draft, 'total_visit_delay_days') !== 0) return 'Enter 0 delay days when no visits were delayed.'
  if (value(draft, 'delayed_visits') > 0 && value(draft, 'total_visit_delay_days') < value(draft, 'delayed_visits')) return 'Total delay days must be at least the number of delayed visits.'
  if (value(draft, 'completed_assessments') > value(draft, 'expected_assessments')) return 'Completed assessments cannot exceed expected assessments.'
  if (value(draft, 'adverse_event_count') === 0 && value(draft, 'adverse_event_burden') !== 0) return 'Enter 0 severity burden when no adverse events occurred.'
  if (value(draft, 'adverse_event_count') > 0 && (value(draft, 'adverse_event_burden') < value(draft, 'adverse_event_count') || value(draft, 'adverse_event_burden') > value(draft, 'adverse_event_count') * 4)) return 'The severity total must match grades 1 through 4 for the adverse events.'
  return ''
}

export function Day30SummaryForm({
  summary,
  busy,
  onSubmit,
  onCancel,
}: {
  summary: Day30Summary | null
  busy: boolean
  onSubmit: (summary: Day30Summary) => Promise<void>
  onCancel?: () => void
}) {
  const [draft, setDraft] = useState(() => initialDraft(summary))
  const [error, setError] = useState('')

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const message = validate(draft)
    if (message) {
      setError(message)
      return
    }
    const payload = Object.fromEntries(fields.map(({ name }) => [name, value(draft, name)])) as unknown as Day30Summary
    await onSubmit(payload)
  }

  return <form className="day30-summary-form" onSubmit={(event) => { void submit(event) }}>
    <div className="compact-section-heading">
      <div><h2>First 30 days</h2><p>Enter totals once. Zero is accepted only when you enter it.</p></div>
      {onCancel ? <button className="text-button" type="button" onClick={onCancel}>Cancel</button> : null}
    </div>
    <div className="day30-input-groups">
      {groups.map((group) => <fieldset key={group.title}>
        <legend>{group.title}</legend>
        <div className="day30-input-row">
          {group.names.map((name) => {
            const field = fields.find((candidate) => candidate.name === name)!
            return <label key={name}>{field.label}<input name={name} type="number" min={field.min} max={field.max} step={field.step ?? 1} value={draft[name]} onChange={(event) => { setDraft((current) => ({ ...current, [name]: event.target.value })); setError('') }} required /></label>
          })}
        </div>
      </fieldset>)}
    </div>
    {error ? <div className="form-error" role="alert">{error}</div> : null}
    <div className="day30-form-actions">
      <span>{draft.scheduled_doses && draft.missed_doses ? `${draft.missed_doses} of ${draft.scheduled_doses} doses missed` : 'Dose total not entered'}</span>
      <button className="primary-button" type="submit" disabled={busy}>{busy ? 'Calculating…' : summary ? 'Recalculate estimate' : 'Calculate estimate'}</button>
    </div>
  </form>
}
