import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CohortAtlasPage } from '../pages/CohortAtlasPage'
import { RecruitmentOverviewPage } from '../pages/RecruitmentOverviewPage'

vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ token: 'token' }) }))

function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }) }
afterEach(() => vi.unstubAllGlobals())

const overview = {
  trial_version_id: 'trial-v1', trial: { registry_id: 'SYN-001', title: 'A long generated respiratory retention study title', version: 2 },
  screening_counts: { potentially_eligible: 6, needs_review: 3, likely_ineligible: 1 },
  retention: { eligible_total: 6, linked_predictions: 4, unlinked_eligible: 2, risk_bands: { lower: 2, near_threshold: 1, higher: 1 }, model_version: 'dropout-xgboost:1', horizon_day: 90, band_policy_version: 'r5-risk-bands-v1' },
}

const run = { run_id: 'r6-active', active: true, status: 'ready', contract_version: 'r6-v3', generated_at: '2026-08-20', screening_date: '2026-08-20', member_count: 750, trial_count: 20, pair_count: 15000, engine_version: 'engine-1', representations: {}, message: null }
const points = [
  { member_id: 'member-1', label: 'Participant 0001', date_of_birth: '1980-01-01', sex: 'female', conditions: ['asthma'], cluster_label: 'fact_cluster_0', is_noise: false, x: -1, y: 1 },
  { member_id: 'member-2', label: 'Participant 0002', date_of_birth: '1970-01-01', sex: 'male', conditions: ['hypertension'], cluster_label: null, is_noise: true, x: 1, y: -1 },
]
const clusters = { run_id: run.run_id, representation: 'patient_fact', representation_version: 'facts-v1', display_projection_only: true, distance_distribution: {}, selected_parameters: { eps: 0.6, min_samples: 10 }, selection_reason: 'bounded selection', cluster_count: 1, noise_fraction: 0.5, clusters: [{ label: 'fact_cluster_0', size: 1 }], points, condition_composition: [] }

describe('population research pages', () => {
  it('reconciles deterministic screening totals with explicit linked prediction denominators', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(json([overview]))))
    render(<MemoryRouter initialEntries={['/research/recruitment']}><RecruitmentOverviewPage /></MemoryRouter>)

    expect(await screen.findByRole('heading', { name: overview.trial.title })).toBeInTheDocument()
    expect(screen.getByText('4/6')).toBeInTheDocument()
    expect(screen.getByLabelText('4 of 6 potentially eligible screenings have predictions')).toBeInTheDocument()
    expect(
      screen.getByText((_, element) => element?.textContent === 'Model dropout-xgboost:1'),
    ).toBeInTheDocument()
    expect(screen.getByText(/never turns a retention prediction into a screening result/i)).toBeInTheDocument()
  })

  it('renders the two-space Atlas and retrieves exact neighbors for a selected member', async () => {
    const fetchMock = vi.fn((input: string, init?: RequestInit) => {
      if (input.endsWith('/cohorts/runs')) return Promise.resolve(json({ status: 'ready', active_run_id: run.run_id, message: null, runs: [run] }))
      if (input.includes('/clusters?')) return Promise.resolve(json(clusters))
      if (input.includes('/members?')) return Promise.resolve(json({ run_id: run.run_id, representation: 'patient_fact', total: 750, offset: 0, limit: 50, members: points }))
      if (input.endsWith('/members/member-1')) return Promise.resolve(json({ run_id: run.run_id, member_id: 'member-1', label: 'Participant 0001', date_of_birth: '1980-01-01', sex: 'female', conditions: ['asthma'], representations: { patient_fact: { cluster_label: 'fact_cluster_0', is_noise: false, x: -1, y: 1 }, screening_profile: { cluster_label: 'screening_cluster_0', is_noise: false, x: .5, y: .2 } } }))
      if (input.endsWith('/similarity/queries') && init?.method === 'POST') return Promise.resolve(json({ run_id: run.run_id, representation: 'patient_fact', query_member_id: 'member-1', index_metadata: { index_type: 'IndexFlatIP', vector_count: 750, dimension: 97 }, neighbors: [{ rank: 1, member_id: 'member-3', label: 'Participant 0003', cosine_similarity: .991, feature_differences: [{ feature: 'observation:hba1c:value', query_value: 5.5, neighbor_value: 5.7, absolute_difference: .2 }] }] }))
      throw new Error(`unexpected request ${input}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/research/cohorts']}><CohortAtlasPage /></MemoryRouter>)

    expect(await screen.findByRole('img', { name: /PCA display projection of 2 generated reference participants/ })).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Inspect Participant 0001' }))
    expect(await screen.findByText('Participant 0003')).toBeInTheDocument()
    expect(screen.getByText('0.991')).toBeInTheDocument()
    expect(screen.getByText(/not eligibility evidence or recommendations/i)).toBeInTheDocument()
  })

  it('deep-links a saved screening as an external overlay without inserting it into the cohort', async () => {
    vi.stubGlobal('fetch', vi.fn((input: string) => {
      if (input.endsWith('/cohorts/runs')) return Promise.resolve(json({ status: 'ready', active_run_id: run.run_id, message: null, runs: [run] }))
      if (input.includes('/clusters?')) return Promise.resolve(json(clusters))
      if (input.includes('/members?')) return Promise.resolve(json({ run_id: run.run_id, representation: 'patient_fact', total: 750, offset: 0, limit: 50, members: points }))
      if (input.endsWith('/cohort-context')) return Promise.resolve(json({ run_id: run.run_id, representation: 'patient_fact', representation_version: 'facts-v1', out_of_sample: true, association: { cluster_label: null, is_unassigned: true, eps: .6, nearest_core_member_id: null, nearest_core_distance: null, competing_labels: [], method: 'dbscan_core_radius_v1' }, projection: { x: .2, y: .4, display_only: true }, vector_checksum: 'checksum', unsupported_concepts: [], disclaimer: 'context' }))
      if (input.endsWith('/similarity')) return Promise.resolve(json({ run_id: run.run_id, representation: 'patient_fact', representation_version: 'facts-v1', out_of_sample: true, query_vector_checksum: 'checksum', unsupported_concepts: [], index_metadata: { index_type: 'IndexFlatIP', vector_count: 750, dimension: 97 }, neighbors: [], disclaimer: 'similarity' }))
      throw new Error(`unexpected request ${input}`)
    }))
    render(<MemoryRouter initialEntries={['/research/cohorts?screening=screen-1&representation=patient_fact']}><CohortAtlasPage /></MemoryRouter>)

    expect(await screen.findByRole('heading', { name: /Unassigned under the frozen core-radius rule/i })).toBeInTheDocument()
    expect(screen.getByText(/was not inserted into the 750-member reference run/i)).toBeInTheDocument()
    expect(screen.getByText(/The saved screening remains outside the reference cohort/i)).toBeInTheDocument()
  })
})
