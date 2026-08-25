import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Search } from 'lucide-react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { IconButton, PageHeader, StateMessage, TechnicalDetails } from '../components/UiPrimitives'

describe('R5A shared UI primitives', () => {
  it('keeps page orientation compact and optional', () => {
    render(
      <MemoryRouter>
        <PageHeader title="Patients" back={{ label: 'Overview', to: '/' }} actions={<button>Add patient</button>} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Patients' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '← Overview' })).toHaveAttribute('href', '/')
    expect(screen.queryByText(/undefined/i)).not.toBeInTheDocument()
  })

  it('announces errors without presenting them as empty data', () => {
    render(<StateMessage state="error" title="Patients could not be loaded">Try again.</StateMessage>)
    expect(screen.getByRole('alert')).toHaveTextContent('Patients could not be loaded')
  })

  it('keeps implementation details collapsed by default', () => {
    render(<TechnicalDetails>Version metadata</TechnicalDetails>)
    const disclosure = screen.getByText('Technical details').closest('details')
    expect(disclosure).not.toHaveAttribute('open')
  })

  it('requires a readable label for icon-only actions', async () => {
    const action = vi.fn()
    render(<IconButton label="Search records" icon={Search} onClick={action} />)
    await userEvent.click(screen.getByRole('button', { name: 'Search records' }))
    expect(action).toHaveBeenCalledOnce()
  })
})
