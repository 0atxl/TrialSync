import { render, screen, waitFor, within } from '@testing-library/react'
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
  beforeEach(() => {
    const preferences = new Map<string, string>()
    vi.stubEnv('VITE_API_BASE_URL', '/api/v1')
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => preferences.get(key) ?? null,
      setItem: (key: string, value: string) => preferences.set(key, value),
      removeItem: (key: string) => preferences.delete(key),
      clear: () => preferences.clear(),
    })
    sessionStorage.clear()
  })
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

  it('redirects an unauthenticated workspace request to sign in', () => {
    renderRoute('/screenings')
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('collapses the navigation, persists the preference, and keeps sign out in the sidebar', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json([])))
    const { container } = renderRoute('/')
    await screen.findByText('No saved screenings')
    const sidebar = screen.getByRole('complementary', { name: 'Primary navigation' })
    expect(sidebar).toContainElement(screen.getByRole('button', { name: 'Sign out' }))
    await userEvent.click(screen.getByRole('button', { name: 'Collapse navigation' }))
    expect(container.querySelector('.app-shell')).toHaveClass('sidebar-collapsed')
    expect(localStorage.getItem('trialsync_sidebar_collapsed')).toBe('true')
    expect(screen.getByRole('button', { name: 'Expand navigation' })).toBeInTheDocument()
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

  it('shows a recoverable error when a stale backend omits presentation details', async () => {
    authenticate()
    const staleResponse = { ...screening, patient_snapshot: undefined, trial_version: undefined }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(staleResponse)))
    renderRoute('/screenings/screen-1')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Restart the TrialSync backend so it loads the latest API and migration',
    )
    expect(screen.queryByText(/Unexpected Application Error/i)).not.toBeInTheDocument()
  })

  it('shows expired sessions as an error rather than an empty history', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ error: { message: 'Expired' } }, 401)))
    renderRoute('/screenings')
    expect(await screen.findByRole('alert')).toHaveTextContent('Your session has expired')
  })

  it('calculates batch pairs from multi-select inputs and submits the selected IDs', async () => {
    authenticate()
    const unscreened = { ...patient, id: 'p2', external_id: 'SYN-002', display_name: 'Synthetic Unscreened' }
    const draftTrial = { ...trial, id: 't2', registry_id: 'SYN-DRAFT', title: 'Draft-only study', versions: [{ ...trial.versions[0], id: 'v2', status: 'draft' }] }
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/patients')) return Promise.resolve(json([patient, unscreened]))
      if (input.endsWith('/trials')) return Promise.resolve(json([trial, draftTrial]))
      if (input.endsWith('/screening-batches') && options?.method === 'POST') return Promise.resolve(json({ id: 'batch-1' }, 201))
      return Promise.resolve(json({ ...batch, id: 'batch-1' }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/batches/new')
    await screen.findByRole('group', { name: 'Patients' })
    expect(screen.getByRole('checkbox', { name: /Synthetic Unscreened/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /Draft-only study/i })).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox', { name: /Synthetic Unscreened/i }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Synthetic age study/i }))
    expect(screen.getByText('1 screening pair')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Run batch screening' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(true))
    const request = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({ patient_ids: ['p2'], trial_version_ids: ['v1'] })
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

  it('filters patient records immediately and links to the focused creation flow', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json([
      patient,
      { ...patient, id: 'p2', external_id: 'SYN-002', display_name: 'Synthetic Grace' },
    ])))
    renderRoute('/patients')
    expect(await screen.findByText('Synthetic Ada')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Add patient' })).toHaveAttribute('href', '/patients/new')
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search patients' }), 'Grace')
    expect(screen.queryByText('Synthetic Ada')).not.toBeInTheDocument()
    expect(screen.getByText('Synthetic Grace')).toBeInTheDocument()
  })

  it('requires confirmation before creating a same-name patient and omits a manual ID', async () => {
    authenticate()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json({ error: { code: 'PATIENT_NAME_REVIEW_REQUIRED', message: 'Review duplicate' } }, 409))
      .mockResolvedValueOnce(json(patient, 201))
      .mockResolvedValueOnce(json(patient))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/new')
    await userEvent.type(screen.getByRole('textbox', { name: 'Display name' }), 'Synthetic Ada')
    await userEvent.click(screen.getByRole('button', { name: 'Create patient' }))
    expect(await screen.findByRole('dialog', { name: 'Review this patient name' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Create distinct patient' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    const initialBody = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
    const confirmedBody = JSON.parse(String(fetchMock.mock.calls[1][1]?.body))
    expect(initialBody).not.toHaveProperty('external_id')
    expect(confirmedBody.confirm_duplicate_name).toBe(true)
  })

  it('confirms patient deletion and returns to the patient workspace', async () => {
    authenticate()
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (options?.method === 'DELETE') return Promise.resolve(new Response(null, { status: 204 }))
      if (input.endsWith('/patients')) return Promise.resolve(json([]))
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')
    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Delete patient' }))
    expect(screen.getByText(/screening snapshots and their evidence history will remain/i)).toBeInTheDocument()
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete patient' }))
    expect(await screen.findByRole('heading', { name: 'Patients' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'DELETE')).toBe(true)
  })

  it('explains when saved screening history protects a trial from deletion', async () => {
    authenticate()
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (options?.method === 'DELETE') return Promise.resolve(json({ error: { code: 'TRIAL_HAS_SCREENING_HISTORY', message: 'Protected' } }, 409))
      return Promise.resolve(json(trial))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/trials/t1')
    await screen.findByRole('heading', { name: 'Synthetic age study' })
    await userEvent.click(screen.getByRole('button', { name: 'Delete trial' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete trial' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('used by saved screening history')
  })
})
