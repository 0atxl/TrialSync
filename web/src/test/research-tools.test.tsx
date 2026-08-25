import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { RiskContext, Screening } from '../api/client'
import { ResearchToolsPanel } from '../components/ResearchToolsPanel'

const screening: Screening = {
  id: 'screen-1', batch_id: null, patient_snapshot_id: 'snapshot-1', trial_version_id: 'version-1',
  overall_state: 'potentially_eligible', screening_date: '2026-08-20', engine_version: 'engine-1',
  dsl_version: 'dsl-1', terminology_version: 'terms-1', unit_version: 'units-1', created_at: '2026-08-20T00:00:00Z',
  counts: { pass_count: 1, fail_count: 0, unknown_count: 0 }, evaluations: [],
  patient_snapshot: {
    id: 'snapshot-1', external_id: 'TS-001', display_name: 'Synthetic participant',
    date_of_birth: '1980-01-01', sex: 'female',
    facts: [
      { id: 'fact-1', patient_id: 'patient-1', fact_type: 'condition', concept: 'asthma', value_numeric: null, value_text: null, unit: null, assertion: 'present', effective_date: '2026-08-20', source_label: 'Reviewed intake', created_at: '', updated_at: '' },
    ],
  },
  trial_version: { registry_id: 'TS-R001', title: 'Respiratory follow-up study', version: 1 },
}

const model = {
  id: 'model-1', name: 'dropout-xgboost', version: '1', alias: 'r5_runtime', candidate_id: 'xgboost-05',
  training_dataset_version: 'r3-dataset-contract-v1', feature_schema_version: 'r4-day30-features-v1',
  threshold: 0.21347740292549133, horizon_day: 90, validation_status: 'approved_runtime_choice',
  metrics: {}, band_policy_version: 'r5-risk-bands-v1', artifact_status: 'ready' as const,
  artifact_message: null, created_at: '2026-08-20T00:00:00Z',
}

const enrollment = {
  id: 'enrollment-1', screening_id: 'screen-1', enrollment_date: '2026-08-20', observation_cutoff_day: 30,
  prediction_horizon_day: 90, feature_contract_version: 'r4-day30-features-v1', tracking_status: 'active' as const,
  missing_baseline_features: [], created_at: '2026-08-20T00:00:00Z',
  baseline: [{ name: 'condition_category', group: 'baseline' as const, value: 'respiratory', source: 'approved_trial_version', missing: false }],
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => vi.unstubAllGlobals())
const renderTools = () => render(<MemoryRouter><ResearchToolsPanel screening={screening} token="token" /></MemoryRouter>)

describe('saved-screening research tools', () => {
  it('runs cohort context and exact similarity as independent screening actions', async () => {
    const fetchMock = vi.fn((input: string) => {
      if (input.endsWith('/cohort-context')) return Promise.resolve(json({
        run_id: 'r6-v3-active', representation: 'patient_fact', representation_version: 'facts-v1', out_of_sample: true,
        association: { cluster_label: 'fact_cluster_2', is_unassigned: false, eps: 0.42, nearest_core_member_id: 'member-core', nearest_core_distance: 0.18, competing_labels: [], method: 'dbscan_core_radius_v1' },
        projection: { x: 1.2, y: -0.4, display_only: true }, vector_checksum: 'abc', unsupported_concepts: [], disclaimer: 'context',
      }))
      if (input.endsWith('/similarity')) return Promise.resolve(json({
        run_id: 'r6-v3-active', representation: 'patient_fact', representation_version: 'facts-v1', out_of_sample: true,
        query_vector_checksum: 'abc', unsupported_concepts: [], index_metadata: { index_type: 'IndexFlatIP', vector_count: 750, dimension: 97 },
        neighbors: [{ rank: 1, member_id: 'member-1', label: 'Reference participant 001', cosine_similarity: 0.982, feature_differences: [{ feature: 'age_band', query_value: 3, neighbor_value: 2, absolute_difference: 1, criterion_context: null }] }], disclaimer: 'similarity',
      }))
      throw new Error(`unexpected request ${input}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderTools()

    await userEvent.click(screen.getByRole('button', { name: 'View cohort context' }))
    expect(await screen.findByText('fact cluster 2')).toBeInTheDocument()
    expect(screen.getByText(/not a diagnosis, phenotype, priority score, or eligibility result/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Find similar participants' }))
    expect(await screen.findByText('Reference participant 001')).toBeInTheDocument()
    expect(screen.getByText(/not screening evidence, a clinical recommendation, or a predicted outcome/i)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('requests all enrollment-owned baseline values with an explicit source', async () => {
    let linked = false
    let enrollmentBody: Record<string, unknown> | null = null
    const unlinked: RiskContext = { screening_id: screening.id, status: 'unlinked', enrollment: null, follow_up: null, model }
    const linkedContext: RiskContext = { screening_id: screening.id, status: 'incomplete', enrollment, follow_up: null, model }
    vi.stubGlobal('fetch', vi.fn((input: string, init?: RequestInit) => {
      if (input.includes('/risk/screenings/') && input.endsWith('/context')) return Promise.resolve(json(linked ? linkedContext : unlinked))
      if (input.endsWith('/enrollment') && init?.method === 'POST') {
        enrollmentBody = JSON.parse(String(init.body)); linked = true; return Promise.resolve(json(enrollment, 201))
      }
      if (input.endsWith('/events')) return Promise.resolve(json({ dose_events: [], visit_events: [], measurements: [], adverse_events: [] }))
      if (input.includes('/risk/predictions?')) return Promise.resolve(json([]))
      throw new Error(`unexpected request ${input}`)
    }))
    renderTools()
    await userEvent.click(screen.getByRole('button', { name: 'Predict dropout risk' }))
    expect(await screen.findByText('Follow-up not started')).toBeInTheDocument()
    expect(screen.getByText(/Missing fields are rejected rather than replaced with zero/i)).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Site region'), 'west')
    await userEvent.selectOptions(screen.getByLabelText('Treatment arm'), 'active')
    await userEvent.type(screen.getByLabelText(/^Baseline functional severity/), '0.3')
    await userEvent.type(screen.getByLabelText(/^Patient-reported burden/), '0.2')
    await userEvent.type(screen.getByLabelText(/^Baseline treatment burden/), '2')
    await userEvent.type(screen.getByLabelText(/^Travel\/access burden/), '2')
    await userEvent.type(screen.getByLabelText(/^Support availability/), '1')
    await userEvent.click(screen.getByRole('button', { name: 'Start research follow-up' }))

    await waitFor(() => expect(enrollmentBody).not.toBeNull())
    const baseline = (enrollmentBody as unknown as { baseline: Record<string, { value: unknown; source: string }> }).baseline
    expect(Object.keys(baseline)).toHaveLength(7)
    expect(Object.values(baseline).every((value) => value.source === 'Research follow-up intake')).toBe(true)
    expect(await screen.findByText('Linked baseline context')).toBeInTheDocument()
  })

  it('shows unresolved day-30 fields explicitly and renders the saved XGBoost prediction beside eligibility', async () => {
    const followUp = {
      id: 'follow-1', research_enrollment_id: enrollment.id, cutoff_day: 30, feature_schema_version: 'r4-day30-features-v1',
      feature_snapshot_hash: 'hash', event_set_checksum: 'events', status: 'ready' as const, missing_features: [], created_at: '', features: [],
    }
    const prediction = {
      id: 'prediction-1', screening_id: screening.id, research_enrollment_id: enrollment.id, follow_up_snapshot_id: followUp.id,
      risk_type: 'trial_dropout_by_day90', probability: 0.64, threshold: model.threshold, research_label: 'higher',
      observation_cutoff_day: 30, horizon_day: 90, model: { name: model.name, version: model.version, alias: model.alias, candidate_id: model.candidate_id },
      feature_schema_version: model.feature_schema_version, feature_snapshot_hash: 'hash', created_at: '',
      top_contributions: [{ feature: 'missed_visit_rate', value: 0.5, shap_value: 0.18, direction: 'higher' }], disclaimer: 'Research only',
    }
    vi.stubGlobal('fetch', vi.fn((input: string) => {
      if (input.includes('/risk/screenings/')) return Promise.resolve(json({ screening_id: screening.id, status: 'ready', enrollment, follow_up: followUp, model }))
      if (input.endsWith('/events')) return Promise.resolve(json({ dose_events: [{}], visit_events: [{}], measurements: [{}], adverse_events: [] }))
      if (input.includes('/risk/predictions?')) return Promise.resolve(json([prediction]))
      throw new Error(`unexpected request ${input}`)
    }))
    renderTools()
    await userEvent.click(screen.getByRole('button', { name: 'Predict dropout risk' }))

    expect(await screen.findByText('64.0%')).toBeInTheDocument()
    expect(screen.getAllByText(/xgboost-05/i).length).toBeGreaterThan(0)
    expect(screen.getByText('Missed-visit rate')).toBeInTheDocument()
    expect(screen.getByText(/Eligibility remains potentially eligible/i)).toBeInTheDocument()
    expect(screen.getByText(/does not establish a cause/i)).toBeInTheDocument()
  })

  it('keeps missing day-30 values visible and does not enable inference', async () => {
    const incomplete = {
      id: 'follow-incomplete', research_enrollment_id: enrollment.id, cutoff_day: 30,
      feature_schema_version: 'r4-day30-features-v1', feature_snapshot_hash: null,
      event_set_checksum: 'events-empty', status: 'incomplete',
      missing_features: ['latest_functional_severity', 'missed_dose_rate'], created_at: '',
      features: [
        { name: 'latest_functional_severity', group: 'day30_follow_up', value: null, source: null, missing: true },
        { name: 'missed_dose_rate', group: 'day30_follow_up', value: null, source: null, missing: true },
      ],
    }
    vi.stubGlobal('fetch', vi.fn((input: string) => {
      if (input.includes('/risk/screenings/')) return Promise.resolve(json({ screening_id: screening.id, status: 'incomplete', enrollment, follow_up: incomplete, model }))
      if (input.endsWith('/events')) return Promise.resolve(json({ dose_events: [], visit_events: [], measurements: [], adverse_events: [] }))
      if (input.includes('/risk/predictions?')) return Promise.resolve(json([]))
      throw new Error(`unexpected request ${input}`)
    }))
    renderTools()
    await userEvent.click(screen.getByRole('button', { name: 'Predict dropout risk' }))

    expect(await screen.findByText('2 features unresolved')).toBeInTheDocument()
    expect(screen.getByText(/Latest functional severity · Missed-dose rate/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Predict dropout risk' })).toHaveLength(1)
  })

  it('shows a real loading state and a degraded cohort request as an error', async () => {
    let resolveRequest!: (response: Response) => void
    const pending = new Promise<Response>((resolve) => { resolveRequest = resolve })
    vi.stubGlobal('fetch', vi.fn(() => pending))
    renderTools()
    await userEvent.click(screen.getByRole('button', { name: 'View cohort context' }))

    expect(screen.getByText(/Building the frozen recorded facts projection/)).toBeInTheDocument()
    resolveRequest(json({ error: { code: 'RESEARCH_COHORT_DEGRADED', message: 'The active cohort run is unavailable.' } }, 503))
    expect(await screen.findByRole('alert')).toHaveTextContent('The active cohort run is unavailable.')
    expect(screen.queryByText(/No dense-group association/)).not.toBeInTheDocument()
  })
})
