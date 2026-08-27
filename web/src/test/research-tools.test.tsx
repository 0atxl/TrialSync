import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Day30Summary, RiskContext, Screening } from '../api/client'
import { ResearchRiskPanel } from '../components/ResearchRiskPanel'
import { ResearchToolsPanel } from '../components/ResearchToolsPanel'

const screening: Screening = {
  id: 'screen-1', batch_id: null, patient_snapshot_id: 'snapshot-1', trial_version_id: 'version-1',
  overall_state: 'potentially_eligible', screening_date: '2026-08-20', engine_version: 'engine-1',
  dsl_version: 'dsl-1', terminology_version: 'terms-1', unit_version: 'units-1', created_at: '2026-08-20T00:00:00Z',
  counts: { pass_count: 1, fail_count: 0, unknown_count: 0 }, evaluations: [],
  patient_snapshot: {
    id: 'snapshot-1', external_id: 'TS-001', display_name: 'Avery Brooks', date_of_birth: '1980-01-01', sex: 'female',
    facts: [{ id: 'fact-1', patient_id: 'patient-1', fact_type: 'condition', concept: 'asthma', value_numeric: null, value_text: null, unit: null, assertion: 'present', effective_date: '2026-08-20', source_label: 'Reviewed intake', created_at: '', updated_at: '' }],
  },
  trial_version: { registry_id: 'TS-R001', title: 'Respiratory follow-up study', version: 1 },
}

const model = {
  id: 'model-1', name: 'dropout-xgboost', version: '1', alias: 'r5_runtime', candidate_id: 'xgboost-05',
  training_dataset_version: 'r3-dataset-contract-v1', feature_schema_version: 'r4-day30-features-v1',
  threshold: 0.21347740292549133, horizon_day: 90, validation_status: 'approved_runtime_choice', metrics: {},
  band_policy_version: 'r5-risk-bands-v1', artifact_status: 'ready' as const, artifact_message: null, created_at: '',
}

const enrollment = {
  id: 'enrollment-1', screening_id: 'screen-1', enrollment_date: '2026-08-20', observation_cutoff_day: 30,
  prediction_horizon_day: 90, feature_contract_version: 'r4-day30-features-v1', tracking_status: 'active' as const,
  missing_baseline_features: [], created_at: '',
  baseline: [{ name: 'condition_category', group: 'baseline' as const, value: 'respiratory', source: 'approved_trial_version', missing: false }],
}

const summary: Day30Summary = {
  scheduled_doses: 8, missed_doses: 2, scheduled_visits: 4, missed_visits: 1, delayed_visits: 1,
  total_visit_delay_days: 2, expected_assessments: 4, completed_assessments: 3,
  latest_functional_severity: 0.4, latest_assessment_day: 30, adverse_event_count: 0, adverse_event_burden: 0,
}

const followUp = {
  id: 'follow-1', research_enrollment_id: enrollment.id, cutoff_day: 30, feature_schema_version: 'r4-day30-features-v1',
  feature_snapshot_hash: 'hash', event_set_checksum: 'summary-hash', input_summary: summary, status: 'ready' as const,
  missing_features: [], created_at: '', features: [],
}

const prediction = {
  id: 'prediction-1', screening_id: screening.id, research_enrollment_id: enrollment.id, follow_up_snapshot_id: followUp.id,
  risk_type: 'trial_dropout_by_day90' as const, probability: 0.516, threshold: model.threshold, research_label: 'higher' as const,
  observation_cutoff_day: 30, horizon_day: 90, model: { name: model.name, version: model.version, alias: model.alias, candidate_id: model.candidate_id },
  feature_schema_version: model.feature_schema_version, feature_snapshot_hash: 'hash', created_at: '',
  top_contributions: [{ feature: 'missed_dose_rate', value: 0.25, shap_value: 0.18, direction: 'higher' as const }], disclaimer: '',
}

const scenarios = {
  follow_up_snapshot_id: followUp.id, scenario: 'additional_missed_doses' as const, threshold: model.threshold, horizon_day: 90,
  points: [
    { additional_missed_doses: 0, scheduled_doses: 8, missed_doses: 2, missed_dose_rate: 0.25, probability: 0.516 },
    { additional_missed_doses: 1, scheduled_doses: 9, missed_doses: 3, missed_dose_rate: 1 / 3, probability: 0.516 },
    { additional_missed_doses: 2, scheduled_doses: 10, missed_doses: 4, missed_dose_rate: 0.4, probability: 0.56 },
  ],
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())
const renderTools = () => render(<MemoryRouter><ResearchToolsPanel screening={screening} token="token" /></MemoryRouter>)
const renderRisk = () => render(<MemoryRouter><ResearchRiskPanel screening={screening} token="token" /></MemoryRouter>)

describe('saved-screening research tools', () => {
  it('links each independent action to its workspace', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(json({ screening_id: screening.id, status: 'unlinked', enrollment: null, follow_up: null, model }))))
    renderTools()
    expect(await screen.findByText('Not started')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Dropout follow-up/i })).toHaveAttribute('href', '/screenings/screen-1/dropout')
    expect(screen.getByRole('link', { name: /Cohort context/i })).toHaveAttribute('href', expect.stringContaining('tool=cohort'))
    expect(screen.getByRole('link', { name: /Similar participants/i })).toHaveAttribute('href', expect.stringContaining('tool=similarity'))
  })

  it('saves sourced baseline values, then opens one aggregate form', async () => {
    let linked = false
    let enrollmentBody: { baseline: Record<string, { source: string }> } | null = null
    const unlinked: RiskContext = { screening_id: screening.id, status: 'unlinked', enrollment: null, follow_up: null, model }
    const linkedContext: RiskContext = { screening_id: screening.id, status: 'incomplete', enrollment, follow_up: null, model }
    vi.stubGlobal('fetch', vi.fn((input: string, init?: RequestInit) => {
      if (input.includes('/risk/screenings/') && input.endsWith('/context')) return Promise.resolve(json(linked ? linkedContext : unlinked))
      if (input.endsWith('/enrollment') && init?.method === 'POST') { enrollmentBody = JSON.parse(String(init.body)); linked = true; return Promise.resolve(json(enrollment, 201)) }
      throw new Error(`unexpected request ${input}`)
    }))
    renderRisk()
    expect(await screen.findByText('Complete baseline setup')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Site region'), 'west')
    await userEvent.selectOptions(screen.getByLabelText('Treatment arm'), 'active')
    for (const [label, value] of [['Baseline functional severity', '0.3'], ['Patient-reported burden', '0.2'], ['Treatment burden', '2'], ['Travel and access burden', '2'], ['Available support', '1']]) await userEvent.type(screen.getByLabelText(new RegExp(`^${label}`)), value)
    await userEvent.click(screen.getByRole('button', { name: 'Start follow-up' }))
    await waitFor(() => expect(enrollmentBody).not.toBeNull())
    expect(Object.values(enrollmentBody!.baseline).every((item) => item.source === 'Research follow-up intake')).toBe(true)
    expect(await screen.findByText('First 30 days')).toBeInTheDocument()
    expect(screen.getByLabelText('Doses missed')).toHaveValue(null)
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('submits explicit totals and renders exact current and missed-dose scenarios', async () => {
    let submitted: Day30Summary | null = null
    vi.stubGlobal('fetch', vi.fn((input: string, init?: RequestInit) => {
      if (input.includes('/risk/screenings/')) return Promise.resolve(json({ screening_id: screening.id, status: 'incomplete', enrollment, follow_up: null, model }))
      if (input.endsWith('/day30-summary') && init?.method === 'POST') { submitted = JSON.parse(String(init.body)); return Promise.resolve(json(followUp, 201)) }
      if (input.endsWith('/risk/predictions') && init?.method === 'POST') return Promise.resolve(json(prediction, 201))
      if (input.endsWith('/risk/scenarios') && init?.method === 'POST') return Promise.resolve(json(scenarios))
      throw new Error(`unexpected request ${input}`)
    }))
    renderRisk()
    expect(await screen.findByText('First 30 days')).toBeInTheDocument()
    for (const [name, value] of Object.entries(summary)) {
      const input = document.querySelector<HTMLInputElement>(`input[name="${name}"]`)!
      await userEvent.type(input, String(value))
    }
    await userEvent.click(screen.getByRole('button', { name: 'Calculate estimate' }))
    await waitFor(() => expect(submitted).toEqual(summary))
    expect(await screen.findAllByText('51.6%')).toHaveLength(3)
    expect(screen.getByText('If more doses are missed')).toBeInTheDocument()
    expect(screen.getByText('56.0%')).toBeInTheDocument()
    expect(screen.getByText('2/8')).toBeInTheDocument()
    expect(screen.getByText('4/10')).toBeInTheDocument()
  })

  it('loads a saved result and keeps model details collapsed', async () => {
    vi.stubGlobal('fetch', vi.fn((input: string) => {
      if (input.includes('/risk/screenings/')) return Promise.resolve(json({ screening_id: screening.id, status: 'ready', enrollment, follow_up: followUp, model }))
      if (input.includes('/risk/predictions?')) return Promise.resolve(json([prediction]))
      if (input.endsWith('/risk/scenarios')) return Promise.resolve(json(scenarios))
      throw new Error(`unexpected request ${input}`)
    }))
    renderRisk()
    expect(await screen.findAllByText('51.6%')).toHaveLength(3)
    expect(screen.getByText('Raised estimate')).toBeInTheDocument()
    expect(screen.getByText(/xgboost-05/i)).not.toBeVisible()
    await userEvent.click(screen.getByText('Technical details'))
    expect(screen.getByText(/xgboost-05/i)).toBeVisible()
  })
})
