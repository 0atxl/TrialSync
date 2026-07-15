import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { routes } from '../app/router'
import { AuthProvider } from '../auth/AuthContext'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

const patient = { id: 'p1', external_id: 'SYN-001', display_name: 'Synthetic Ada', date_of_birth: null, sex: null, facts: [] }
const trial = { id: 't1', registry_id: 'SYN-T1', title: 'Synthetic age study', condition: 'Synthetic', phase: null, versions: [{ id: 'v1', version: 1, status: 'approved', source_text: null, criteria: [] }] }
const snapshot = { id: 's1', external_id: 'SYN-001', display_name: 'Synthetic Ada', date_of_birth: null, sex: null, facts: [] }
const evaluation = { id: 'e1', criterion_id: 'c1', criterion_order: 1, criterion_kind: 'inclusion' as const, criterion_source_text: 'Age 18 to 75 years', result: 'unknown' as const, truth: 'unknown', reason_code: 'MISSING_FACT', canonical_explanation: 'The criterion is unknown because the date of birth is not recorded.', evidence: [], rejected_evidence: [], missing_information: [{ fact: 'date_of_birth', reason: 'MISSING_FACT', detail: 'Date of birth is required to calculate age.' }] }
const screening = {
  id: 'screen-1', batch_id: null, patient_snapshot_id: 's1', patient_snapshot: snapshot,
  trial_version_id: 'v1', trial_version: { registry_id: 'SYN-T1', title: 'Synthetic age study', version: 1 },
  overall_state: 'needs_review' as const, screening_date: '2026-07-15', engine_version: '0.1.0', dsl_version: '1.0', terminology_version: '1', unit_version: '1', created_at: '2026-07-15T00:00:00Z',
  counts: { pass_count: 0, fail_count: 0, unknown_count: 1 }, evaluations: [evaluation],
}

function renderRoute(initialPath = '/') {
  return render(<AuthProvider><RouterProvider router={createMemoryRouter(routes, { initialEntries: [initialPath] })} /></AuthProvider>)
}

function authenticate() {
  sessionStorage.setItem('trialsync_access_token', 'test-token')
  sessionStorage.setItem('trialsync_user', JSON.stringify({ id: 'user-1', email: 'demo@example.com', display_name: 'Demo User' }))
}

describe('TrialSync Phase 5 screening workflow', () => {
  beforeEach(() => { vi.stubEnv('VITE_API_BASE_URL', '/api/v1'); sessionStorage.clear() })
  afterEach(() => { vi.unstubAllEnvs(); vi.restoreAllMocks() })

  it('redirects an unauthenticated workspace request to sign in', () => {
    renderRoute('/screenings')
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('loads approved inputs and submits a patient/trial pair', async () => {
    authenticate()
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/patients')) return Promise.resolve(json([patient]))
      if (input.endsWith('/trials')) return Promise.resolve(json([trial]))
      if (input.endsWith('/screenings') && options?.method === 'POST') return Promise.resolve(json(screening, 201))
      return Promise.resolve(json(screening))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/screenings/new')
    const submit = await screen.findByRole('button', { name: 'Run screening' })
    await userEvent.click(submit)
    expect(await screen.findByRole('heading', { name: 'needs review' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(true)
  })

  it('renders cautious states in history and keeps failures visible', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json([
      { ...screening, overall_state: 'potentially_eligible', id: 'pass' },
      { ...screening, overall_state: 'likely_ineligible', id: 'fail' },
      screening,
    ])))
    renderRoute('/screenings')
    expect(await screen.findByText('potentially eligible')).toBeInTheDocument()
    expect(screen.getByText('likely ineligible')).toBeInTheDocument()
    expect(screen.getByText('needs review')).toBeInTheDocument()
  })

  it('shows unknown evidence, missing information, and immutable source labels', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(screening)))
    renderRoute('/screenings/screen-1')
    expect(await screen.findByRole('heading', { name: 'Age 18 to 75 years' })).toBeInTheDocument()
    expect(screen.getByText('Required information is not recorded.')).toBeInTheDocument()
    expect(screen.getByText('Date of birth is required to calculate age.')).toBeInTheDocument()
    expect(screen.getAllByText('Synthetic Ada').length).toBeGreaterThan(0)
  })

  it('shows expired sessions as an error rather than an empty history', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ error: { message: 'Expired' } }, 401)))
    renderRoute('/screenings')
    expect(await screen.findByRole('alert')).toHaveTextContent('Your session has expired')
  })

  it('calculates batch pairs from multi-select inputs and submits the selected IDs', async () => {
    authenticate()
    const prior = { ...screening, id: 'prior-screen' }
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/screenings')) return Promise.resolve(json([prior]))
      if (input.endsWith('/trials')) return Promise.resolve(json([trial]))
      if (input.endsWith('/screening-batches') && options?.method === 'POST') return Promise.resolve(json({ id: 'batch-1' }, 201))
      return Promise.resolve(json({ ...batch, id: 'batch-1' }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/batches/new')
    await screen.findByText('Patient snapshots')
    await userEvent.click(screen.getByRole('checkbox', { name: /Synthetic Ada/i }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Synthetic age study/i }))
    expect(screen.getByText('1 screening pair')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Run batch screening' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(true))
  })

  const batch = {
    id: 'batch-1', label: null, pair_count: 6, created_at: '2026-07-15T00:00:00Z',
    state_counts: { potentially_eligible: 2, likely_ineligible: 2, needs_review: 2 }, unknown_criterion_count: 2,
    screenings: ['s1', 's2', 's3'].flatMap((patientSnapshotId, row) => ['v1', 'v2'].map((trialVersionId, column) => ({
      patient_snapshot_id: patientSnapshotId,
      patient_snapshot: { ...snapshot, id: patientSnapshotId, display_name: `Synthetic ${row + 1}` },
      trial_version_id: trialVersionId,
      trial_version: { registry_id: `SYN-${column + 1}`, title: `Study ${column + 1}`, version: 1 },
      screening_id: `${patientSnapshotId}-${trialVersionId}`,
      overall_state: (['potentially_eligible', 'likely_ineligible', 'needs_review'] as const)[(row + column) % 3],
      counts: { pass_count: 1, fail_count: 0, unknown_count: row === 2 ? 1 : 0 },
    }))),
  }

  it('renders a three by two batch matrix with six links to screening evidence', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(batch)))
    renderRoute('/batches/batch-1')
    expect(await screen.findByRole('table')).toBeInTheDocument()
    const links = screen.getAllByRole('link', { name: /potentially eligible|likely ineligible|needs review/i })
    expect(links).toHaveLength(6)
    expect(links[0]).toHaveAttribute('href', '/screenings/s1-v1')
  })

  it('renders batch API failures without claiming that no results exist', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    renderRoute('/batches/new')
    expect(await screen.findByRole('alert')).toHaveTextContent('Batch screening inputs could not be loaded')
  })
})
