import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { routes } from '../app/router'
import { AuthProvider } from '../auth/AuthContext'
import { ToastProvider } from '../components/ToastProvider'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
})

const patient = {
  id: 'p1',
  external_id: 'SYN-001',
  display_name: 'Synthetic Ada',
  date_of_birth: null,
  sex: null,
  created_at: '2026-07-29T10:00:00Z',
  updated_at: '2026-07-29T10:00:00Z',
  facts: [],
  unsupported_details: [],
  consistency_issues: [],
}
const patientFact = {
  id: 'f1',
  patient_id: 'p1',
  fact_type: 'condition' as const,
  concept: 'pregnancy',
  value_numeric: null,
  value_text: null,
  unit: null,
  assertion: 'absent' as const,
  effective_date: null,
  source_label: 'Manual entry',
  created_at: '2026-07-29T10:00:00Z',
  updated_at: '2026-07-29T10:00:00Z',
}
const metforminFact = {
  ...patientFact,
  id: 'f-metformin',
  fact_type: 'medication' as const,
  concept: 'metformin',
  assertion: 'present' as const,
  effective_date: '2026-07-01',
}
const hba1cFact = {
  ...patientFact,
  id: 'f-hba1c',
  fact_type: 'observation' as const,
  concept: 'hba1c',
  assertion: 'present' as const,
  value_numeric: '7.800000',
  unit: '%',
  effective_date: '2026-07-02',
}
const patientFactCatalog = {
  version: 'pd0-contract-v1',
  entries: [
    {
      key: 'pregnancy',
      fact_type: 'condition' as const,
      concept: 'pregnancy',
      display_label: 'Pregnancy status',
      group: 'conditions' as const,
      input_kind: 'pregnancy_status' as const,
      allowed_assertions: ['present', 'absent', 'unknown'] as const,
      fixed_unit: null,
      allowed_units: [],
      effective_date_required: true,
      screening_supported: true,
      help_text: 'Record the assessed pregnancy status and assessment date.',
      display_order: 50,
    },
    {
      key: 'metformin',
      fact_type: 'medication' as const,
      concept: 'metformin',
      display_label: 'Metformin',
      group: 'medications' as const,
      input_kind: 'status' as const,
      allowed_assertions: ['present', 'absent', 'unknown'] as const,
      fixed_unit: null,
      allowed_units: [],
      effective_date_required: false,
      screening_supported: true,
      help_text: 'Record whether metformin use is present, absent, or unknown.',
      display_order: 10,
    },
    {
      key: 'hba1c',
      fact_type: 'observation' as const,
      concept: 'hba1c',
      display_label: 'HbA1c',
      group: 'observations' as const,
      input_kind: 'numeric' as const,
      allowed_assertions: ['present', 'unknown'] as const,
      fixed_unit: '%',
      allowed_units: [],
      effective_date_required: true,
      screening_supported: true,
      help_text: 'Record the measured HbA1c result.',
      display_order: 10,
    },
    {
      key: 'wbc',
      fact_type: 'observation' as const,
      concept: 'wbc',
      display_label: 'White blood cell count with a deliberately long review label',
      group: 'observations' as const,
      input_kind: 'numeric' as const,
      allowed_assertions: ['present', 'unknown'] as const,
      fixed_unit: '10^9/L',
      allowed_units: [],
      effective_date_required: true,
      screening_supported: true,
      help_text: 'Record the measured white blood cell count.',
      display_order: 20,
    },
  ],
}
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
  return render(
    <AuthProvider>
      <ToastProvider>
        <RouterProvider router={createMemoryRouter(routes, { initialEntries: [initialPath] })} />
      </ToastProvider>
    </AuthProvider>,
  )
}

function authenticate(isCatalogAdmin = false) {
  sessionStorage.setItem('trialsync_access_token', 'test-token')
  sessionStorage.setItem('trialsync_user', JSON.stringify({ id: 'user-1', email: 'demo@example.com', display_name: 'Demo User', is_catalog_admin: isCatalogAdmin }))
}

function withPatientCatalog(
  handler: (input: string, options?: RequestInit) => Promise<Response>,
) {
  return vi.fn((input: string, options?: RequestInit) => {
    if (input.endsWith('/patient-fact-catalog')) {
      return Promise.resolve(json(patientFactCatalog))
    }
    return handler(input, options)
  })
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

  it('fills the public synthetic demo credentials on request', async () => {
    renderRoute('/login')
    await userEvent.click(screen.getByRole('button', { name: /Use demo account/ }))
    expect(screen.getByRole('textbox', { name: 'Email' })).toHaveValue('demo@trialsync.example')
    expect(screen.getByLabelText('Password')).toHaveValue('SyntheticDemo123!')
    expect(screen.getByText('Fills synthetic demonstration credentials')).toBeInTheDocument()
  })

  it('reveals and hides the login password without changing its value', async () => {
    renderRoute('/login')
    const password = screen.getByLabelText('Password')
    await userEvent.type(password, 'SyntheticPassword123!')

    expect(password).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password).toHaveAttribute('type', 'text')
    expect(password).toHaveValue('SyntheticPassword123!')
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(password).toHaveAttribute('type', 'password')
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

  it('uses the single light theme and removes the legacy preference', async () => {
    authenticate()
    localStorage.setItem('trialsync_theme', 'dark')
    document.documentElement.dataset.theme = 'dark'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json([])))
    renderRoute('/')
    await screen.findByText('No saved screenings')
    await waitFor(() => expect(document.documentElement).not.toHaveAttribute('data-theme'))
    expect(localStorage.getItem('trialsync_theme')).toBeNull()
    expect(screen.queryByRole('button', { name: /mode/i })).not.toBeInTheDocument()
  })

  it('shows the Help documentation and active navigation', () => {
    authenticate()
    renderRoute('/help')
    expect(screen.getByRole('heading', { name: 'TrialSync documentation' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Result assistant' })).toBeInTheDocument()
    expect(screen.getByText(/Enter sends a question/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Open API docs' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Help' })).toHaveAttribute('aria-current', 'page')
  })

  it('lets a catalog administrator add a local clinical detail', async () => {
    authenticate(true)
    const created = {
      id: 'concept-crp', key: 'c_reactive_protein', fact_type: 'observation', concept: 'c_reactive_protein',
      display_label: 'C-reactive protein', concept_group: 'observations', input_kind: 'numeric',
      allowed_assertions_json: ['present', 'unknown'], fixed_unit: 'mg/L', effective_date_required: true,
      screening_supported: true, help_text: 'Record the measured C-reactive protein result.',
      display_order: 170, active: true, created_at: '2026-07-30T00:00:00Z', updated_at: '2026-07-30T00:00:00Z',
    }
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/clinical-concepts') && options?.method === 'POST') return Promise.resolve(json(created, 201))
      if (input.endsWith('/clinical-concepts')) return Promise.resolve(json([]))
      return Promise.resolve(json({}))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/catalog')
    expect(await screen.findByRole('heading', { name: 'Clinical catalog' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Catalog' })).toHaveAttribute('aria-current', 'page')
    await userEvent.type(screen.getByLabelText('Display name'), 'C-reactive protein')
    await userEvent.selectOptions(screen.getByLabelText('Category'), 'observation')
    await userEvent.type(screen.getByLabelText('Fixed unit'), 'mg/L')
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    expect(await screen.findByText('Clinical detail added')).toBeInTheDocument()
    const request = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({
      display_label: 'C-reactive protein', fact_type: 'observation', fixed_unit: 'mg/L',
    })
  })

  it('requires an administrator to select a terminology suggestion before saving it locally', async () => {
    authenticate(true)
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.includes('/clinical-concepts/suggestions')) return Promise.resolve(json({
        query: 'metformin', unavailable_sources: [], suggestions: [{
          source: 'rxnorm', code: '6809', display_label: 'metformin', detail: 'RXNORM', fixed_unit: null, score: 100,
        }],
      }))
      if (input.endsWith('/clinical-concepts') && options?.method === 'POST') return Promise.resolve(json({
        id: 'concept-metformin', key: 'metformin_custom', fact_type: 'medication', concept: 'metformin_custom', display_label: 'metformin', concept_group: 'medications', input_kind: 'status', allowed_assertions_json: ['present', 'absent', 'unknown'], fixed_unit: null, effective_date_required: false, screening_supported: true, help_text: 'Record whether metformin is present.', terminology_system: 'rxnorm', terminology_code: '6809', display_order: 50, active: true, created_at: '2026-07-30T00:00:00Z', updated_at: '2026-07-30T00:00:00Z',
      }, 201))
      if (input.endsWith('/clinical-concepts')) return Promise.resolve(json([]))
      return Promise.resolve(json({}))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/catalog')
    await screen.findByRole('heading', { name: 'Clinical catalog' })
    await userEvent.type(screen.getByLabelText('Display name'), 'metformin')
    await userEvent.selectOptions(screen.getByLabelText('Category'), 'medication')
    await userEvent.click(screen.getByRole('button', { name: 'Find RxNorm suggestion' }))
    await userEvent.click(await screen.findByRole('button', { name: /metformin.*RxNorm.*6809/i }))
    expect(screen.getByText(/RxNorm code 6809 selected/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    const request = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({
      terminology_system: 'rxnorm', terminology_code: '6809',
    })
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
    expect(screen.getByText('Synthetic Ada')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Patient facts at screening' })).toBeInTheDocument()
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
    expect(screen.getByRole('link', { name: 'Back to the result assistant' })).toHaveAttribute('href', '#screening-chat-panel')
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
    await userEvent.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByText('Only the stored age criterion is unresolved.')).toBeInTheDocument()
    await waitFor(() => expect(composer).toHaveFocus())
    expect(screen.getByRole('status')).toHaveTextContent('A new result explanation is ready.')
    const request = fetchMock.mock.calls.find(([input]) => input.endsWith('/conversation/messages'))
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ message: 'Why is age unresolved?' })
  })

  it('sends with Enter, preserves Shift+Enter, and reports the character limit', async () => {
    authenticate()
    const emptyConversation = { ...conversation, messages: [] }
    const assistant = { ...conversation.messages[0], id: 'keyboard-response', content: 'Keyboard response ready.' }
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/conversation')) return Promise.resolve(json(emptyConversation))
      if (input.endsWith('/conversation/messages') && options?.method === 'POST') return Promise.resolve(json(assistant, 201))
      return Promise.resolve(json(screening))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/screenings/screen-1')
    const composer = await screen.findByRole('textbox', { name: 'Question about this stored result' })
    await userEvent.type(composer, 'Line one')
    await userEvent.keyboard('{Shift>}{Enter}{/Shift}Line two')
    expect(composer).toHaveValue('Line one\nLine two')
    expect(screen.getByText(/17 \/ 1000 · Enter sends/)).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([input]) => input.endsWith('/conversation/messages'))).toHaveLength(0)
    await userEvent.keyboard('{Enter}')
    expect(await screen.findByText('Keyboard response ready.')).toBeInTheDocument()
    const posts = fetchMock.mock.calls.filter(([input]) => input.endsWith('/conversation/messages'))
    expect(posts).toHaveLength(1)
    expect(JSON.parse(String(posts[0][1]?.body))).toEqual({ message: 'Line one\nLine two' })
  })

  it('preserves and explicitly retries a question after a confirmed no-save failure', async () => {
    authenticate()
    const emptyConversation = { ...conversation, messages: [] }
    const assistant = { ...conversation.messages[0], id: 'retry-response', content: 'The retry succeeded.' }
    let attempts = 0
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/conversation')) return Promise.resolve(json(emptyConversation))
      if (input.endsWith('/conversation/messages') && options?.method === 'POST') {
        attempts += 1
        return Promise.resolve(attempts === 1
          ? json({ error: { code: 'ASSISTANT_TIMEOUT', message: 'Timed out' } }, 504)
          : json(assistant, 201))
      }
      return Promise.resolve(json(screening))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/screenings/screen-1')
    const composer = await screen.findByRole('textbox', { name: 'Question about this stored result' })
    await userEvent.type(composer, 'Explain the unknown criterion')
    await userEvent.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('timed out')
    expect(composer).toHaveValue('Explain the unknown criterion')
    await waitFor(() => expect(composer).toHaveFocus())
    await userEvent.click(screen.getByRole('button', { name: 'Retry question' }))
    expect(await screen.findByText('The retry succeeded.')).toBeInTheDocument()
    expect(attempts).toBe(2)
  })

  it('shows the submitted question and an accessible typing state while waiting', async () => {
    authenticate()
    const emptyConversation = { ...conversation, messages: [] }
    const assistant = {
      ...conversation.messages[0], id: 'message-typing-response',
      content: 'The stored criterion is still unresolved.',
    }
    let resolveAssistant: (response: Response) => void = () => undefined
    const pendingResponse = new Promise<Response>((resolve) => { resolveAssistant = resolve })
    const fetchMock = vi.fn((input: string, options?: RequestInit) => {
      if (input.endsWith('/conversation')) return Promise.resolve(json(emptyConversation))
      if (input.endsWith('/conversation/messages') && options?.method === 'POST') return pendingResponse
      return Promise.resolve(json(screening))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/screenings/screen-1')
    await userEvent.type(await screen.findByRole('textbox', { name: 'Question about this stored result' }), 'Why is this unresolved?')
    await userEvent.click(screen.getByRole('button', { name: 'Send question' }))
    expect(screen.getByText('Why is this unresolved?')).toBeInTheDocument()
    expect(screen.getByText('The result assistant is preparing a response.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Responding…' })).toBeDisabled()
    resolveAssistant(json(assistant, 201))
    expect(await screen.findByText('The stored criterion is still unresolved.')).toBeInTheDocument()
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
    await userEvent.click(screen.getByRole('button', { name: 'Send question' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(copy)
    expect(alert).toHaveClass('chat-error-toast')
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss chat error' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
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
      .mockResolvedValueOnce(json(patientFactCatalog))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/new')
    await userEvent.type(screen.getByRole('textbox', { name: 'Display name' }), 'Synthetic Ada')
    await userEvent.click(screen.getByRole('button', { name: 'Create patient' }))
    expect(await screen.findByRole('dialog', { name: 'Review this patient name' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Create distinct patient' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
    const initialBody = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
    const confirmedBody = JSON.parse(String(fetchMock.mock.calls[1][1]?.body))
    expect(initialBody).not.toHaveProperty('external_id')
    expect(confirmedBody.confirm_duplicate_name).toBe(true)
    expect(await screen.findByText('Synthetic Ada is ready for structured clinical details.')).toBeInTheDocument()
  })

  it('creates canonical biological sex through a keyboard-operable radio group', async () => {
    authenticate()
    const createdPatient = { ...patient, sex: 'male' as const }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json(createdPatient, 201))
      .mockResolvedValueOnce(json(createdPatient))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/new')

    await userEvent.type(screen.getByRole('textbox', { name: 'Display name' }), 'Synthetic Radio')
    const sexGroup = screen.getByRole('group', { name: 'Biological sex for screening' })
    const female = within(sexGroup).getByRole('radio', { name: 'Female' })
    const male = within(sexGroup).getByRole('radio', { name: 'Male' })
    female.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(male).toBeChecked()

    await userEvent.click(screen.getByRole('button', { name: 'Create patient' }))
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
    expect(body.sex).toBe('male')
  })

  it('rejects a future date of birth before creating a patient', async () => {
    authenticate()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/new')

    await userEvent.type(screen.getByRole('textbox', { name: 'Display name' }), 'Synthetic Future')
    fireEvent.change(screen.getByLabelText('Date of birth'), { target: { value: '2099-01-01' } })
    await userEvent.click(screen.getByRole('button', { name: 'Create patient' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Date of birth cannot be in the future')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('locks repeated profile submissions and confirms the exact saved change', async () => {
    authenticate()
    let resolvePatch!: (response: Response) => void
    const patchResponse = new Promise<Response>((resolve) => { resolvePatch = resolve })
    const updatedPatient = {
      ...patient,
      display_name: 'Synthetic Ada Updated',
      updated_at: '2026-07-29T10:01:00Z',
    }
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') return patchResponse
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Edit demographics' }))
    const name = screen.getByRole('textbox', { name: 'Display name' })
    await userEvent.clear(name)
    await userEvent.type(name, updatedPatient.display_name)
    const save = screen.getByRole('button', { name: 'Save changes' })
    fireEvent.click(save)
    fireEvent.click(save)

    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'PATCH')).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled()

    resolvePatch(json(updatedPatient))
    expect(await screen.findByText(
      'Display name changed from Synthetic Ada to Synthetic Ada Updated.',
    )).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit demographics' })).toBeEnabled()
  })

  it('cancels a controlled demographic edit without changing the review surface', async () => {
    authenticate()
    const fetchMock = withPatientCatalog(() => Promise.resolve(json(patient)))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    expect(screen.getAllByText('Not recorded')).toHaveLength(2)
    await userEvent.click(screen.getByRole('button', { name: 'Edit demographics' }))
    await userEvent.click(screen.getByRole('radio', { name: 'Female' }))
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByRole('button', { name: 'Edit demographics' })).toBeInTheDocument()
    expect(screen.getAllByText('Not recorded')).toHaveLength(2)
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'PATCH')).toHaveLength(0)
  })

  it('shows exact in-page confirmation for several demographic changes', async () => {
    authenticate()
    const updatedPatient = {
      ...patient,
      display_name: 'Synthetic Ada Revised',
      date_of_birth: '1990-05-14',
      sex: 'female' as const,
      updated_at: '2026-07-29T10:02:00Z',
    }
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') return Promise.resolve(json(updatedPatient))
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Edit demographics' }))
    const name = screen.getByRole('textbox', { name: 'Display name' })
    await userEvent.clear(name)
    await userEvent.type(name, updatedPatient.display_name)
    fireEvent.change(screen.getByLabelText('Date of birth'), {
      target: { value: updatedPatient.date_of_birth },
    })
    await userEvent.click(screen.getByRole('radio', { name: 'Female' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    const summaryHeading = await screen.findByText('Patient profile updated')
    const summary = summaryHeading.closest('.change-summary')!
    expect(summary).toHaveTextContent('Patient profile updated')
    expect(summary).toHaveTextContent('Display name changed from Synthetic Ada')
    expect(summary).toHaveTextContent('Date of birth changed from Not recorded to 1990-05-14')
    expect(summary).toHaveTextContent('Biological sex changed from Not recorded to Female')
    const body = JSON.parse(String(
      fetchMock.mock.calls.find(([, options]) => options?.method === 'PATCH')?.[1]?.body,
    ))
    expect(body.expected_updated_at).toBe(patient.updated_at)
  })

  it('retains demographic edits and offers reload after a stale update conflict', async () => {
    authenticate()
    const latestPatient = {
      ...patient,
      sex: 'female' as const,
      updated_at: '2026-07-29T10:03:00Z',
    }
    let patientReads = 0
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') {
        return Promise.resolve(json({
          error: { code: 'PATIENT_RECORD_STALE', message: 'Stale profile' },
        }, 409))
      }
      patientReads += 1
      return Promise.resolve(json(patientReads === 1 ? patient : latestPatient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Edit demographics' }))
    await userEvent.click(screen.getByRole('radio', { name: 'Male' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('changed in another session')
    expect(screen.getByRole('radio', { name: 'Male' })).toBeChecked()
    await userEvent.click(screen.getByRole('button', { name: 'Reload latest profile' }))
    expect(await screen.findByText('Female')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit demographics' })).toBeInTheDocument()
  })

  it('confirms fact addition and removal without reloading the patient record', async () => {
    authenticate()
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'POST') return Promise.resolve(json(patientFact, 201))
      if (options?.method === 'DELETE') return Promise.resolve(new Response(null, { status: 204 }))
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    await userEvent.click(screen.getByRole('button', { name: /Pregnancy status/i }))
    await userEvent.click(screen.getByRole('radio', { name: 'Not pregnant' }))
    await userEvent.click(screen.getByRole('button', { name: 'Add detail' }))
    expect(await screen.findByText('Pregnancy status added: Not pregnant.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
    const body = JSON.parse(String(
      fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')?.[1]?.body,
    ))
    expect(body).toMatchObject({
      catalog_key: 'pregnancy',
      value: { input_kind: 'pregnancy_status', assertion: 'absent' },
      expected_patient_updated_at: patient.updated_at,
    })

    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))
    expect(await screen.findByText(
      'Pregnancy status was removed. Existing saved screenings are unchanged.',
    )).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument()
  })

  it('disables Pregnant for a male patient while keeping explicit alternatives', async () => {
    authenticate()
    const malePatient = { ...patient, sex: 'male' as const }
    const fetchMock = withPatientCatalog(() => Promise.resolve(json(malePatient)))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    await userEvent.click(screen.getByRole('button', { name: /Pregnancy status/i }))

    expect(screen.getByRole('radio', { name: 'Pregnant' })).toBeDisabled()
    expect(screen.getByRole('radio', { name: 'Not pregnant' })).toBeEnabled()
    expect(screen.getByRole('radio', { name: 'Unknown' })).toBeEnabled()
    expect(screen.getByRole('radio', { name: 'Unknown' })).toBeChecked()
    expect(screen.getByRole('note')).toHaveTextContent(
      'Pregnant is unavailable because biological sex is recorded as Male',
    )
  })

  it('allows Pregnant with missing sex and then shows a profile-completeness warning', async () => {
    authenticate()
    const presentPregnancy = {
      ...patientFact,
      assertion: 'present' as const,
      effective_date: '2026-07-29',
    }
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'POST') return Promise.resolve(json(presentPregnancy, 201))
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    await userEvent.click(screen.getByRole('button', { name: /Pregnancy status/i }))

    expect(screen.getByRole('radio', { name: 'Pregnant' })).toBeEnabled()
    expect(screen.getByRole('status')).toHaveTextContent(
      'Biological sex is not recorded. You can save Pregnant',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Add detail' }))

    expect(await screen.findByRole('heading', {
      name: 'Biological sex is not recorded',
    })).toBeInTheDocument()
    expect(screen.getByText(/demographic profile should be completed/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Complete demographics' })).toBeInTheDocument()
  })

  it('shows and resolves a preserved legacy male and Pregnant conflict', async () => {
    authenticate()
    const presentPregnancy = {
      ...patientFact,
      assertion: 'present' as const,
      effective_date: '2026-07-29',
    }
    const legacyPatient = {
      ...patient,
      sex: 'male' as const,
      facts: [presentPregnancy],
      consistency_issues: [{
        code: 'PATIENT_PREGNANCY_SEX_CONFLICT' as const,
        severity: 'conflict' as const,
        message: 'Legacy conflict',
        field: 'pregnancy' as const,
        fact_id: presentPregnancy.id,
      }],
    }
    const reconciled = {
      ...presentPregnancy,
      assertion: 'unknown' as const,
      updated_at: '2026-07-29T10:05:00Z',
    }
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') return Promise.resolve(json(reconciled))
      return Promise.resolve(json(legacyPatient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    expect(await screen.findByRole('heading', {
      name: 'Reconcile biological sex and pregnancy',
    })).toBeInTheDocument()
    expect(screen.getByText(/will not change either one automatically/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Review pregnancy status' }))

    expect(screen.getByRole('dialog', {
      name: 'Edit Pregnancy status',
    })).toBeInTheDocument()
    expect(screen.getByText(/No value was changed automatically/i)).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Pregnant' })).toBeDisabled()
    expect(screen.getByRole('radio', { name: 'Pregnant' })).toBeChecked()
    await userEvent.click(screen.getByRole('radio', { name: 'Unknown' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText(
      'Pregnancy status changed from Pregnant to Unknown.',
    )).toBeInTheDocument()
    expect(screen.queryByRole('heading', {
      name: 'Reconcile biological sex and pregnancy',
    })).not.toBeInTheDocument()
  })

  it('links a blocked sex change to the conflicting pregnancy editor', async () => {
    authenticate()
    const presentPregnancy = {
      ...patientFact,
      assertion: 'present' as const,
      effective_date: '2026-07-29',
    }
    const femalePatient = {
      ...patient,
      sex: 'female' as const,
      facts: [presentPregnancy],
    }
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') {
        return Promise.resolve(json({
          error: {
            code: 'PATIENT_PREGNANCY_SEX_CONFLICT',
            message: 'Conflict',
            field: 'sex',
            details: [{ fact_id: presentPregnancy.id }],
          },
        }, 409))
      }
      return Promise.resolve(json(femalePatient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Edit demographics' }))
    await userEvent.click(screen.getByRole('radio', { name: 'Male' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'cannot be changed to Male while Pregnancy status is Pregnant',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Review pregnancy status' }))
    expect(screen.getByRole('dialog', {
      name: 'Edit Pregnancy status',
    })).toBeInTheDocument()
    expect(screen.getByText(/Review Pregnancy status before changing biological sex/i))
      .toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: 'Male' })).not.toBeInTheDocument()
  })

  it('groups current details with catalog labels and hides internal entry fields', async () => {
    authenticate()
    const populated = {
      ...patient,
      facts: [patientFact, metforminFact, hba1cFact],
    }
    const fetchMock = withPatientCatalog(() => Promise.resolve(json(populated)))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    expect(await screen.findByRole('heading', { name: 'Clinical details' })).toBeInTheDocument()
    const clinicalDetails = screen.getByRole('region', { name: 'Clinical details' })
    expect(screen.getByRole('heading', { name: 'Conditions' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Medications' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Labs and observations' })).toBeInTheDocument()
    expect(within(clinicalDetails).getByText('Pregnancy status')).toBeInTheDocument()
    expect(within(clinicalDetails).getByText('Metformin')).toBeInTheDocument()
    expect(within(clinicalDetails).getByText('7.8%')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Concept' })).not.toBeInTheDocument()
    expect(screen.queryByText('type2_diabetes')).not.toBeInTheDocument()

    await userEvent.type(
      screen.getByRole('searchbox', { name: 'Search current details' }),
      'HbA1c',
    )
    expect(within(clinicalDetails).getByText('HbA1c')).toBeInTheDocument()
    expect(within(clinicalDetails).queryByText('Metformin')).not.toBeInTheDocument()
    await userEvent.click(within(clinicalDetails).getByRole('button', { name: 'Edit' }))
    expect(screen.getByRole('spinbutton', { name: 'Result' })).toHaveValue(7.8)
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  })

  it('renders the numeric catalog control and never sends a client-supplied unit', async () => {
    authenticate()
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'POST') return Promise.resolve(json(hba1cFact, 201))
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Clinical details' })
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    await userEvent.type(
      screen.getByRole('searchbox', { name: 'Search supported details' }),
      'HbA1c',
    )
    await userEvent.click(screen.getByRole('button', { name: /HbA1c/i }))
    expect(screen.getByText('%')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Unit' })).not.toBeInTheDocument()
    await userEvent.type(screen.getByRole('spinbutton', { name: 'Result' }), '7.8')
    await userEvent.click(screen.getByRole('button', { name: 'Add detail' }))

    expect(await screen.findByText('HbA1c added: 7.8%.')).toBeInTheDocument()
    const body = JSON.parse(String(
      fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')?.[1]?.body,
    ))
    expect(body.catalog_key).toBe('hba1c')
    expect(body.value).toMatchObject({
      input_kind: 'numeric',
      assertion: 'present',
      value_numeric: 7.8,
    })
    expect(body).not.toHaveProperty('unit')
    expect(body).not.toHaveProperty('fact_type')
    expect(body).not.toHaveProperty('concept')
  })

  it('saves an unknown observation without rendering or sending a numeric value', async () => {
    authenticate()
    const unknownFact = {
      ...hba1cFact,
      id: 'f-wbc',
      concept: 'wbc',
      assertion: 'unknown' as const,
      value_numeric: null,
      unit: '10^9/L',
    }
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'POST') return Promise.resolve(json(unknownFact, 201))
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Clinical details' })
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    await userEvent.click(screen.getByRole('button', {
      name: /White blood cell count with a deliberately long review label/i,
    }))
    await userEvent.click(screen.getByRole('radio', { name: 'Unknown' }))
    expect(screen.queryByRole('spinbutton', { name: 'Result' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Add detail' }))

    const body = JSON.parse(String(
      fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')?.[1]?.body,
    ))
    expect(body.value).toMatchObject({
      input_kind: 'numeric',
      assertion: 'unknown',
      value_numeric: null,
    })
  })

  it('edits an existing detail with exact feedback and cancel-safe state', async () => {
    authenticate()
    const current = { ...patient, facts: [metforminFact] }
    const changed = {
      ...metforminFact,
      assertion: 'absent' as const,
      updated_at: '2026-07-29T10:03:00Z',
    }
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') return Promise.resolve(json(changed))
      return Promise.resolve(json(current))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    expect(
      within(await screen.findByRole('region', { name: 'Clinical details' }))
        .getByText('Metformin'),
    ).toBeInTheDocument()
    const edit = screen.getByRole('button', { name: 'Edit' })
    await userEvent.click(edit)
    expect(screen.getByRole('radio', { name: 'Present' })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
    await userEvent.click(screen.getByRole('radio', { name: 'Absent' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(within(screen.getByRole('region', { name: 'Clinical details' }))
      .getByText('Present')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.click(screen.getByRole('radio', { name: 'Absent' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText(
      'Metformin changed from Present to Absent.',
    )).toBeInTheDocument()
    const body = JSON.parse(String(
      fetchMock.mock.calls.find(([, options]) => options?.method === 'PATCH')?.[1]?.body,
    ))
    expect(body.expected_fact_updated_at).toBe(metforminFact.updated_at)
    expect(body.value).toMatchObject({ input_kind: 'status', assertion: 'absent' })
  })

  it('redirects a duplicate add attempt into the existing detail editor', async () => {
    authenticate()
    const current = { ...patient, facts: [metforminFact] }
    const changed = { ...metforminFact, assertion: 'absent' as const }
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        return Promise.resolve(json({
          error: {
            code: 'PATIENT_FACT_DUPLICATE',
            message: 'Edit existing',
            details: [{ fact_id: metforminFact.id, catalog_key: 'metformin' }],
          },
        }, 409))
      }
      if (options?.method === 'PATCH') return Promise.resolve(json(changed))
      return Promise.resolve(json(current))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    expect(
      within(await screen.findByRole('region', { name: 'Clinical details' }))
        .getByText('Metformin'),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    await userEvent.click(screen.getByRole('button', { name: /^Metformin/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Add detail' }))
    expect(await screen.findByRole('heading', { name: 'Edit Metformin' })).toBeInTheDocument()
    expect(within(screen.getByRole('dialog', { name: 'Edit Metformin' }))
      .getByRole('status')).toHaveTextContent(
      'already exists. You are now editing the current detail',
    )
    await userEvent.click(screen.getByRole('radio', { name: 'Absent' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Metformin changed from Present to Absent.')).toBeInTheDocument()
  })

  it('retains guided values after a clinical-detail server error', async () => {
    authenticate()
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        return Promise.resolve(json({ error: { code: 'SERVER_ERROR', message: 'No' } }, 500))
      }
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Clinical details' })
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    await userEvent.click(screen.getByRole('button', { name: /HbA1c/i }))
    await userEvent.type(screen.getByRole('spinbutton', { name: 'Result' }), '8.1')
    await userEvent.click(screen.getByRole('button', { name: 'Add detail' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your entered values are still here',
    )
    expect(screen.getByRole('spinbutton', { name: 'Result' })).toHaveValue(8.1)
    expect(screen.getByRole('button', { name: 'Add detail' })).toBeEnabled()
  })

  it('records an unlisted patient detail separately from screening facts', async () => {
    authenticate()
    const unsupported = {
      id: 'unsupported-1',
      patient_id: 'p1',
      category: 'medication' as const,
      label: 'Synthetic study medication',
      context: 'Reported during mentor review',
      source_label: 'Manual review item',
      created_at: '2026-07-29T10:00:00Z',
      updated_at: '2026-07-29T10:00:00Z',
    }
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (input.endsWith('/unsupported-details') && options?.method === 'POST') {
        return Promise.resolve(json(unsupported, 201))
      }
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Clinical details' })
    await userEvent.click(screen.getByRole('button', { name: 'Add clinical detail' }))
    await userEvent.click(screen.getByRole('button', { name: /Detail not listed/i }))
    await userEvent.click(screen.getByRole('radio', { name: 'Medication' }))
    await userEvent.type(
      screen.getByRole('textbox', { name: 'Clinical detail' }),
      'Synthetic study medication',
    )
    await userEvent.type(
      screen.getByRole('textbox', { name: /^Context/ }),
      'Reported during mentor review',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Save for review' }))

    expect(await screen.findByText('Review item recorded')).toBeInTheDocument()
    expect(screen.getByText('Synthetic study medication')).toBeInTheDocument()
    expect(screen.getByText('Review only')).toBeInTheDocument()
    const request = fetchMock.mock.calls.find(
      ([input, options]) =>
        input.endsWith('/unsupported-details') && options?.method === 'POST',
    )
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      category: 'medication',
      label: 'Synthetic study medication',
      context: 'Reported during mentor review',
    })
    expect(fetchMock.mock.calls.some(
      ([input, options]) => input.endsWith('/facts') && options?.method === 'POST',
    )).toBe(false)
  })

  it('keeps failed profile values inline and presents one assertive error announcement', async () => {
    authenticate()
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') {
        return Promise.resolve(json({ error: { code: 'SERVER_ERROR', message: 'No' } }, 500))
      }
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Edit demographics' }))
    const name = screen.getByRole('textbox', { name: 'Display name' })
    await userEvent.clear(name)
    await userEvent.type(name, 'Synthetic Retained Value')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    const alerts = await screen.findAllByRole('alert')
    expect(alerts).toHaveLength(1)
    expect(alerts[0]).toHaveTextContent('Your entered values are still here')
    expect(name).toHaveValue('Synthetic Retained Value')
    expect(screen.getByText('Profile not saved')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeEnabled()
  })

  it('asks before leaving a patient record with unsaved changes', async () => {
    authenticate()
    const fetchMock = withPatientCatalog((input: string) => {
      if (input.endsWith('/patients')) return Promise.resolve(json([patient]))
      return Promise.resolve(json(patient))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients/p1')

    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Edit demographics' }))
    const name = screen.getByRole('textbox', { name: 'Display name' })
    await userEvent.type(name, ' changed')
    const backLink = document.querySelector<HTMLAnchorElement>('.back-link')
    expect(backLink).not.toBeNull()
    await userEvent.click(backLink!)

    const unsavedDialog = screen.getByRole('dialog', { name: 'Discard unsaved changes?' })
    expect(unsavedDialog).toBeInTheDocument()
    await userEvent.click(within(unsavedDialog).getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('heading', { name: 'Synthetic Ada' })).toBeInTheDocument()

    await userEvent.clear(name)
    await userEvent.type(name, 'Synthetic Ada')
    await userEvent.click(backLink!)
    expect(await screen.findByRole('heading', { name: 'Patients' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: 'Discard unsaved changes?' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('link', { name: 'Review record' }))
    await screen.findByRole('heading', { name: 'Synthetic Ada' })
    await userEvent.click(screen.getByRole('button', { name: 'Edit demographics' }))
    const reopenedName = screen.getByRole('textbox', { name: 'Display name' })
    await userEvent.type(reopenedName, ' changed again')
    await userEvent.click(document.querySelector<HTMLAnchorElement>('.back-link')!)
    await userEvent.click(screen.getByRole('button', { name: 'Discard changes' }))
    expect(await screen.findByRole('heading', { name: 'Patients' })).toBeInTheDocument()
  })

  it('confirms patient deletion and returns to the patient workspace', async () => {
    authenticate()
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
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
    expect(screen.getByText(
      'Synthetic Ada was removed from the active workspace. Saved screenings are unchanged.',
    )).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'DELETE')).toBe(true)
  })

  it('explains when saved screening history protects a trial from deletion', async () => {
    authenticate()
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
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
    await userEvent.type(screen.getByRole('textbox', { name: 'Source text' }), 'Patient name: Synthetic Import Ada')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze for review' }))
    expect(await screen.findByRole('heading', { name: 'Review extracted patient candidates' })).toBeInTheDocument()
    const analyzeCall = fetchMock.mock.calls.find(([input, options]) => input.endsWith('/imports') && options?.method === 'POST')
    expect(JSON.parse(String(analyzeCall?.[1]?.body))).toMatchObject({ kind: 'patient', source_type: 'text' })
  })

  it('persists candidate edits before approving an imported patient', async () => {
    authenticate()
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
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
    await userEvent.click(screen.getByRole('radio', { name: 'Female' }))
    await userEvent.click(screen.getByRole('button', { name: 'Approve and create patient' }))
    expect(await screen.findByRole('heading', { name: 'Synthetic Ada' })).toBeInTheDocument()
    const updateCall = fetchMock.mock.calls.find(([, options]) => options?.method === 'PUT')
    expect(JSON.parse(String(updateCall?.[1]?.body)).candidates.profile.display_name).toBe('Synthetic Edited Import')
    expect(JSON.parse(String(updateCall?.[1]?.body)).candidates.profile.sex).toBe('female')
    expect(fetchMock.mock.calls.some(([input]) => input.endsWith('/imports/import-1/approve'))).toBe(true)
  })

  it('rejects a future date of birth before approving an imported patient', async () => {
    authenticate()
    const fetchMock = vi.fn().mockResolvedValue(json(importReview))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/imports/import-1')
    const dateOfBirth = await screen.findByLabelText('Date of birth')
    fireEvent.change(dateOfBirth, { target: { value: '2099-01-01' } })
    await userEvent.click(screen.getByRole('button', { name: 'Approve and create patient' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Date of birth cannot be in the future.',
    )
    expect(
      fetchMock.mock.calls.some(([, options]) => options?.method === 'PUT'),
    ).toBe(false)
  })

  it('rejects oversized PDFs before attempting an upload', async () => {
    authenticate()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/imports/new?kind=trial')
    await userEvent.click(screen.getByRole('radio', { name: 'Upload PDF' }))
    const file = new File([new Uint8Array(5_000_001)], 'oversized.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText(/PDF document/i), { target: { files: [file] } })
    await userEvent.click(screen.getByRole('button', { name: 'Analyze for review' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('5 MB PDF limit')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('explains when OCR cannot recover readable text', async () => {
    authenticate()
    const fetchMock = vi.fn().mockResolvedValue(json({
      error: { code: 'OCR_NO_TEXT', message: 'No machine-readable text was found.' },
    }, 422))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/imports/new?kind=patient')
    await userEvent.click(screen.getByRole('radio', { name: 'Upload PDF' }))
    const file = new File(['%PDF-1.4 synthetic scan fixture'], 'scan-like.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText(/PDF document/i), { target: { files: [file] } })
    fireEvent.submit(screen.getByRole('button', { name: 'Analyze for review' }).closest('form') as HTMLFormElement)
    expect(await screen.findByRole('alert')).toHaveTextContent('OCR could not recover')
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('saves imported criteria through the simple protocol workflow', async () => {
    authenticate()
    const criterion = {
      id: 'c-age',
      kind: 'inclusion' as const,
      order: 1,
      source_text: 'Age between 18 and 75 years',
      normalized_rule: {
        op: 'between',
        fact: 'demographic.age',
        min: 18,
        max: 75,
        unit: 'year',
      },
      required: true,
    }
    const draft = {
      ...trial,
      versions: [{ ...trial.versions[0], status: 'draft' as const, criteria: [criterion] }],
    }
    const approved = {
      ...trial,
      versions: [{ ...trial.versions[0], status: 'approved' as const, criteria: [criterion] }],
    }
    let updated = false
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (options?.method === 'PUT') { updated = true; return Promise.resolve(json(approved)) }
      return Promise.resolve(json(updated ? approved : draft))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/trials/t1')
    await screen.findByRole('button', { name: 'Save protocol' })
    await userEvent.click(screen.getByRole('button', { name: 'Save protocol' }))
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Save protocol' }))
        .not.toBeInTheDocument())
    expect(screen.getByText('Protocol saved')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(true)
  })

  it('builds a guided deterministic criterion without codes, units, or order fields', async () => {
    authenticate()
    const draft = { ...trial, versions: [{ ...trial.versions[0], status: 'draft' as const, criteria: [] }] }
    const criterion = {
      id: 'c-age', kind: 'inclusion', order: 1, source_text: 'Age 18 to 75 years',
      normalized_rule: { op: 'between', fact: 'demographic.age', min: 18, max: 75, unit: 'year' },
      required: true,
    }
    const populated = {
      ...draft,
      versions: [{ ...draft.versions[0], criteria: [criterion] }],
    }
    let updated = false
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (input.includes('/guided-criteria') && options?.method === 'POST') {
        updated = true
        return Promise.resolve(json(criterion, 201))
      }
      if (input.endsWith('/trials/t1')) {
        return Promise.resolve(json(updated ? populated : draft))
      }
      return Promise.resolve(json(draft))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/trials/t1')
    const inclusion = (await screen.findByRole('heading', { name: 'Inclusion criteria' }))
      .closest('section')!
    await userEvent.click(within(inclusion).getByRole('button', { name: 'Add criterion' }))
    await userEvent.click(screen.getByRole('button', { name: /^Age/i }))
    expect(screen.queryByRole('spinbutton', { name: 'Order' })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Normalized concept' })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Unit' })).not.toBeInTheDocument()
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Add criterion' }),
    )
    await screen.findByText('Criterion added')
    const request = fetchMock.mock.calls.find(
      ([input, options]) => input.includes('/guided-criteria') && options?.method === 'POST',
    )
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({
      kind: 'inclusion',
      subject_key: 'age',
      operator: 'between',
      minimum: 18,
      maximum: 75,
    })
  })

  it('does not persist an invalid guided numeric criterion', async () => {
    authenticate()
    const draft = { ...trial, versions: [{ ...trial.versions[0], status: 'draft' as const, criteria: [] }] }
    const fetchMock = withPatientCatalog(() => Promise.resolve(json(draft)))
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/trials/t1')
    const inclusion = (await screen.findByRole('heading', { name: 'Inclusion criteria' }))
      .closest('section')!
    await userEvent.click(within(inclusion).getByRole('button', { name: 'Add criterion' }))
    await userEvent.click(screen.getByRole('button', { name: /^Age/i }))
    const minimum = screen.getByRole('spinbutton', { name: 'Minimum' })
    await userEvent.clear(minimum)
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Add criterion' }),
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a range')
    expect(fetchMock.mock.calls.some(
      ([input, options]) => input.includes('/guided-criteria') && options?.method === 'POST',
    )).toBe(false)
  })

  it('keeps an unsupported trial criterion as review-only without a screening rule', async () => {
    authenticate()
    const draft = {
      ...trial,
      versions: [{ ...trial.versions[0], status: 'draft' as const, criteria: [] }],
    }
    const unsupported = {
      id: 'c-unsupported',
      kind: 'exclusion' as const,
      order: 1,
      source_text: 'Prior synthetic procedure within 30 days',
      normalized_rule: null,
      required: true,
    }
    const populated = {
      ...draft,
      versions: [{ ...draft.versions[0], criteria: [unsupported] }],
    }
    let updated = false
    const fetchMock = withPatientCatalog((input: string, options?: RequestInit) => {
      if (input.includes('/unsupported-criteria') && options?.method === 'POST') {
        updated = true
        return Promise.resolve(json(unsupported, 201))
      }
      return Promise.resolve(json(updated ? populated : draft))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/trials/t1')

    const exclusion = (await screen.findByRole('heading', { name: 'Exclusion criteria' }))
      .closest('section')!
    await userEvent.click(within(exclusion).getByRole('button', { name: 'Add criterion' }))
    await userEvent.click(screen.getByRole('button', { name: /Criterion not listed/i }))
    await userEvent.type(
      screen.getByRole('textbox', { name: 'Protocol wording' }),
      'Prior synthetic procedure within 30 days',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Save for review' }))

    expect(await screen.findByText('Criterion saved for review')).toBeInTheDocument()
    expect(within(exclusion).getByText('Prior synthetic procedure within 30 days'))
      .toBeInTheDocument()
    expect(within(exclusion).getByText(/Review only · no screening rule/i))
      .toBeInTheDocument()
    const request = fetchMock.mock.calls.find(
      ([input, options]) =>
        input.includes('/unsupported-criteria') && options?.method === 'POST',
    )
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      kind: 'exclusion',
      category: 'condition',
      source_text: 'Prior synthetic procedure within 30 days',
    })
  })
})
