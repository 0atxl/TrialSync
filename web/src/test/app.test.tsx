import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { routes } from '../app/router'
import { AuthProvider } from '../auth/AuthContext'

function renderRoute(initialPath = '/') {
  return render(
    <AuthProvider>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [initialPath] })} />
    </AuthProvider>,
  )
}

function authenticate() {
  sessionStorage.setItem('trialsync_access_token', 'test-token')
  sessionStorage.setItem(
    'trialsync_user',
    JSON.stringify({ id: 'user-1', email: 'demo@example.com', display_name: 'Demo User' }),
  )
}

describe('TrialSync Phase 2 routes', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', '/api/v1')
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.restoreAllMocks()
  })

  it('redirects unauthenticated workspace access to sign in', () => {
    renderRoute('/patients')
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('registers and enters the protected workspace', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            access_token: 'new-token',
            token_type: 'bearer',
            user: { id: 'u1', email: 'new@example.com', display_name: 'New Researcher' },
          }),
          { status: 201, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )
    renderRoute('/register')
    await userEvent.type(screen.getByLabelText('Display name'), 'New Researcher')
    await userEvent.type(screen.getByLabelText('Email'), 'new@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'CorrectHorse123')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Available workflows')).toBeInTheDocument()
  })

  it('renders patient loading, populated, and creation workflows', async () => {
    authenticate()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            { id: 'p1', external_id: 'SYN-001', display_name: 'Synthetic Ada', facts: [] },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 'p2' }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)
    renderRoute('/patients')
    expect(await screen.findByText('Synthetic Ada')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Synthetic ID'), 'SYN-002')
    await userEvent.type(screen.getByLabelText('Display name'), 'Synthetic Bea')
    await userEvent.click(screen.getByRole('button', { name: 'Add patient' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  })

  it('shows API failures as errors rather than empty data', async () => {
    authenticate()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    renderRoute('/trials')
    expect(await screen.findByRole('alert')).toHaveTextContent('Trials could not be loaded')
  })

  it('renders the not-found route for authenticated users', () => {
    authenticate()
    renderRoute('/not-a-route')
    expect(screen.getByRole('heading', { name: /route does not exist/i })).toBeInTheDocument()
  })
})
