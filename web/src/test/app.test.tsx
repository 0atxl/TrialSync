import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
const importReview = {
  id: 'import-1', kind: 'patient' as const, source_type: 'text' as const, status: 'needs_review' as const,
  filename: null, mime_type: 'text/plain', size_bytes: 80, checksum: 'abc',
  source_text: 'Patient name: Synthetic Import Ada\nHbA1c: 8.2 %',
  pages: [{ page: 1, start_offset: 0, end_offset: 52, text: 'Patient name: Synthetic Import Ada\nHbA1c: 8.2 %' }],
  candidates: {
    profile: { display_name: 'Synthetic Import Ada', date_of_birth: null, sex: null },
    facts: [{ candidate_id: 'candidate-1', selected: true, fact_type: 'observation' as const, concept: 'HbA1c', value_numeric: '8.2', value_text: null, unit: '%', assertion: 'present' as const, effective_date: null, source: { span_id: 'span-1', page: 1, start: 35, end: 48, text: 'HbA1c: 8.2 %' }, warnings: [] }],
  },
  warnings: [], quality: { page_count: 1, character_count: 52 }, approved_resource_id: null, created_at: '2026-07-15T00:00:00Z',
}
const conversation = {
  screening_id: 'screen-1',
  provider: { enabled: true, provider: 'canonical', model: 'deterministic-canonical-1', prompt_version: 'screening-chat-v1' },
  suggested_questions: ['Why does this result have its current state?', 'What information is missing?'],
  max_messages: 10,
  max_message_chars: 1000,
  messages: [{
    id: 'message-1', role: 'assistant' as const,
    content: 'The age criterion is unknown because date of birth is missing.',
    answer_state: 'supported' as const,
    citations: [{ criterion_id: 'c1', evaluation_id: 'e1', evidence_ids: [], label: 'Age is unresolved' }],
    provider: { enabled: true, provider: 'canonical', model: 'deterministic-canonical-1', prompt_version: 'screening-chat-v1' },
    created_at: '2026-07-15T10:00:00Z', suggested_questions: [],
  }],
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

  it('restores persisted explanation messages and focuses cited criterion evidence', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn((input: string) => Promise.resolve(
      json(input.endsWith('/conversation') ? conversation : screening),
    )))
    renderRoute('/screenings/screen-1')
    expect(await screen.findByText('Result explanation')).toBeInTheDocument()
    const citation = screen.getByRole('link', { name: /Criterion evidence · Age is unresolved/i })
    await userEvent.click(citation)
    expect(screen.getByRole('article')).toHaveFocus()
  })

  it('posts only the current question and appends the grounded response', async () => {
    authenticate()
    const emptyConversation = { ...conversation, messages: [] }
    const assistant = {
      ...conversation.messages[0], id: 'message-2',
      content: 'Only the stored age criterion is unresolved.',
      suggested_questions: ['Which criteria passed?'],
    }
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/conversation')) return Promise.resolve(json(emptyConversation))
      if (input.endsWith('/conversation/messages') && options?.method === 'POST') return Promise.resolve(json(assistant, 201))
      return Promise.resolve(json(screening))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/screenings/screen-1')
    const composer = await screen.findByRole('textbox', { name: 'Question about this stored result' })
    await userEvent.type(composer, 'Why is age unresolved?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask about result' }))
    expect(await screen.findByText('Only the stored age criterion is unresolved.')).toBeInTheDocument()
    const request = fetchMock.mock.calls.find(([input]) => input.endsWith('/conversation/messages'))
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ message: 'Why is age unresolved?' })
  })

  it('distinguishes insufficient evidence, refusal, and a disabled assistant', async () => {
    authenticate()
    const safeStates = {
      ...conversation,
      provider: { ...conversation.provider, enabled: false, provider: 'disabled', model: null },
      messages: [
        { ...conversation.messages[0], id: 'insufficient', answer_state: 'insufficient_evidence' as const, content: 'The record does not contain that information.', citations: [] },
        { ...conversation.messages[0], id: 'refused', answer_state: 'refused' as const, content: 'I cannot give enrollment advice.', citations: [] },
      ],
    }
    vi.stubGlobal('fetch', vi.fn((input: string) => Promise.resolve(
      json(input.endsWith('/conversation') ? safeStates : screening),
    )))
    renderRoute('/screenings/screen-1')
    expect(await screen.findByText('Not enough evidence')).toBeInTheDocument()
    expect(screen.getByText('Request declined')).toBeInTheDocument()
    expect(screen.getByText('Conversational assistant disabled')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Question about this stored result' })).toBeDisabled()
  })

  it.each([
    ['ASSISTANT_TIMEOUT', 'timed out'],
    ['ASSISTANT_RATE_LIMITED', 'rate-limited'],
    ['ASSISTANT_PROVIDER_ERROR', 'provider is unavailable'],
    ['ASSISTANT_RESPONSE_INVALID', 'could not be safely grounded'],
  ])('renders %s as a system error rather than an empty answer', async (code, copy) => {
    authenticate()
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/conversation')) return Promise.resolve(json({ ...conversation, messages: [] }))
      if (input.endsWith('/conversation/messages') && options?.method === 'POST') {
        return Promise.resolve(json({ error: { code, message: 'Provider failure' } }, 502))
      }
      return Promise.resolve(json(screening))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/screenings/screen-1')
    await userEvent.type(await screen.findByRole('textbox', { name: 'Question about this stored result' }), 'Explain this result')
    await userEvent.click(screen.getByRole('button', { name: 'Ask about result' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(copy)
    expect(screen.queryByText('Result explanation')).not.toBeInTheDocument()
  })

  it('confirms clear conversation and leaves the criterion table visible', async () => {
    authenticate()
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (options?.method === 'DELETE') return Promise.resolve(new Response(null, { status: 204 }))
      return Promise.resolve(json(input.endsWith('/conversation') ? conversation : screening))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/screenings/screen-1')
    await userEvent.click(await screen.findByRole('button', { name: 'Clear conversation' }))
    expect(screen.getByRole('dialog', { name: 'Clear this conversation?' })).toBeInTheDocument()
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Clear conversation' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'DELETE')).toBe(true))
    expect(screen.getByRole('heading', { name: 'Age 18 to 75 years' })).toBeInTheDocument()
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

  it('analyzes pasted synthetic text and opens the review workspace', async () => {
    authenticate()
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/imports') && options?.method === 'POST') return Promise.resolve(json(importReview, 201))
      return Promise.resolve(json(importReview))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/imports/new?kind=patient')
    await userEvent.type(screen.getByRole('textbox', { name: 'Synthetic source text' }), 'Patient name: Synthetic Import Ada')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze for review' }))
    expect(await screen.findByRole('heading', { name: 'Review extracted patient candidates' })).toBeInTheDocument()
    const analyzeCall = fetchMock.mock.calls.find(([input, options]) => input.endsWith('/imports') && options?.method === 'POST')
    expect(JSON.parse(String(analyzeCall?.[1]?.body))).toMatchObject({ kind: 'patient', source_type: 'text' })
  })

  it('persists candidate edits before approving an imported patient', async () => {
    authenticate()
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/imports/import-1') && options?.method === 'PUT') {
        const body = JSON.parse(String(options.body))
        return Promise.resolve(json({ ...importReview, candidates: body.candidates }))
      }
      if (input.endsWith('/imports/import-1/approve')) return Promise.resolve(json({ kind: 'patient', resource_id: 'p1', review_id: 'import-1' }))
      if (input.endsWith('/patients/p1')) return Promise.resolve(json(patient))
      return Promise.resolve(json(importReview))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/imports/import-1')
    const name = await screen.findByRole('textbox', { name: 'Display name' })
    await userEvent.clear(name)
    await userEvent.type(name, 'Synthetic Edited Import')
    await userEvent.click(screen.getByRole('button', { name: 'Approve and create patient' }))
    expect(await screen.findByRole('heading', { name: 'Synthetic Ada' })).toBeInTheDocument()
    const updateCall = fetchMock.mock.calls.find(([, options]) => options?.method === 'PUT')
    expect(JSON.parse(String(updateCall?.[1]?.body)).candidates.profile.display_name).toBe('Synthetic Edited Import')
    expect(fetchMock.mock.calls.some(([input]) => input.endsWith('/imports/import-1/approve'))).toBe(true)
  })

  it('rejects oversized PDFs before attempting an upload', async () => {
    authenticate()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/imports/new?kind=trial')
    await userEvent.click(screen.getByRole('radio', { name: 'Upload PDF' }))
    const file = new File([new Uint8Array(5_000_001)], 'oversized.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText(/Text-based PDF/i), { target: { files: [file] } })
    await userEvent.click(screen.getByRole('button', { name: 'Analyze for review' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('5 MB PDF limit')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('explains when a selected PDF requires unavailable OCR', async () => {
    authenticate()
    const fetchMock = vi.fn().mockResolvedValue(json({
      error: { code: 'PDF_OCR_NOT_ENABLED', message: 'No machine-readable text was found.' },
    }, 422))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/imports/new?kind=patient')
    await userEvent.click(screen.getByRole('radio', { name: 'Upload PDF' }))
    const file = new File(['%PDF-1.4 synthetic scan fixture'], 'scan-like.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText(/Text-based PDF/i), { target: { files: [file] } })
    fireEvent.submit(screen.getByRole('button', { name: 'Analyze for review' }).closest('form') as HTMLFormElement)
    expect(await screen.findByRole('alert')).toHaveTextContent('OCR is not enabled')
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('provides an explicit approval action for imported draft trial versions', async () => {
    authenticate()
    const draft = { ...trial, versions: [{ ...trial.versions[0], status: 'draft' as const }] }
    const approved = { ...trial, versions: [{ ...trial.versions[0], status: 'approved' as const }] }
    let updated = false
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (options?.method === 'PUT') { updated = true; return Promise.resolve(json(approved)) }
      return Promise.resolve(json(updated ? approved : draft))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/trials/t1')
    await screen.findByRole('button', { name: 'Approve version' })
    await userEvent.click(screen.getByRole('button', { name: 'Approve version' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Approve version' })).not.toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(true)
  })
})
