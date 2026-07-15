import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { routes } from '../app/router'

function renderRoute(initialPath = '/') {
  return render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [initialPath] })} />)
}

describe('TrialSync routed foundation', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('renders the configured foundation overview', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://api.example.test/api/v1/')

    renderRoute()

    expect(
      screen.getByRole('heading', { name: /a dependable base for evidence-first screening/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('API · http://api.example.test/api/v1')).toBeInTheDocument()
  })

  it('renders the patient placeholder at its URL route', () => {
    vi.stubEnv('VITE_API_BASE_URL', '/api/v1')
    renderRoute('/patients')

    expect(screen.getByRole('heading', { name: 'Patients' })).toBeInTheDocument()
    expect(screen.getByText(/will arrive in Phase 2/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Patients' })).toHaveAttribute('href', '/patients')
  })

  it('shows a configuration error instead of a false success state', () => {
    vi.stubEnv('VITE_API_BASE_URL', '')

    renderRoute()

    expect(screen.getByRole('alert')).toHaveTextContent('VITE_API_BASE_URL is required')
  })

  it('renders the not-found route', () => {
    vi.stubEnv('VITE_API_BASE_URL', '/api/v1')

    renderRoute('/not-a-route')

    expect(screen.getByRole('heading', { name: /route does not exist/i })).toBeInTheDocument()
  })
})
