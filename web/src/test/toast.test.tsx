import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider, useToast } from '../components/ToastProvider'

function ToastHarness({ onAction = () => undefined }: { onAction?: () => void }) {
  const { showToast } = useToast()

  return (
    <div>
      <button
        type="button"
        onClick={() =>
          showToast({ variant: 'success', title: 'Profile saved', message: 'Change complete.' })
        }
      >
        Show success
      </button>
      <button
        type="button"
        onClick={() =>
          showToast({
            variant: 'warning',
            title: 'Review change',
            message: 'Check this detail.',
            action: { label: 'Review detail', onClick: onAction },
          })
        }
      >
        Show action
      </button>
      <button
        type="button"
        onClick={() =>
          showToast({ variant: 'error', title: 'Save failed', message: 'Try again.' })
        }
      >
        Show error
      </button>
      <button
        type="button"
        onClick={() => {
          for (let index = 1; index <= 4; index += 1) {
            showToast({
              variant: 'warning',
              title: `Queued ${index}`,
              message: `Notification ${index}`,
            })
          }
        }}
      >
        Queue four
      </button>
    </div>
  )
}

function renderHarness(onAction?: () => void) {
  return render(
    <ToastProvider>
      <ToastHarness onAction={onAction} />
    </ToastProvider>,
  )
}

describe('application toast feedback', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('announces success, pauses its remaining timeout, and supports manual dismissal', () => {
    vi.useFakeTimers()
    renderHarness()

    fireEvent.click(screen.getByRole('button', { name: 'Show success' }))
    const toast = screen.getByRole('status')
    expect(toast).toHaveTextContent('Profile saved')

    act(() => vi.advanceTimersByTime(3000))
    fireEvent.mouseEnter(toast)
    act(() => vi.advanceTimersByTime(10000))
    expect(screen.getByRole('status')).toBeInTheDocument()

    fireEvent.mouseLeave(toast)
    act(() => vi.advanceTimersByTime(1999))
    expect(screen.getByRole('status')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(1))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Show success' }))
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss profile saved notification' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('gives errors a longer timeout while retaining manual dismissal', () => {
    vi.useFakeTimers()
    renderHarness()

    fireEvent.click(screen.getByRole('button', { name: 'Show error' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Save failed')
    act(() => vi.advanceTimersByTime(9999))
    expect(screen.getByRole('alert')).toHaveTextContent('Try again.')
    act(() => vi.advanceTimersByTime(1))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('runs an optional action and dismisses its notification', () => {
    const onAction = vi.fn()
    renderHarness(onAction)

    fireEvent.click(screen.getByRole('button', { name: 'Show action' }))
    fireEvent.click(screen.getByRole('button', { name: 'Review detail' }))

    expect(onAction).toHaveBeenCalledOnce()
    expect(screen.queryByText('Check this detail.')).not.toBeInTheDocument()
  })

  it('shows no more than three notifications and advances the queue after dismissal', () => {
    renderHarness()

    fireEvent.click(screen.getByRole('button', { name: 'Queue four' }))
    const viewport = screen.getByRole('region', { name: 'Notifications' })
    expect(within(viewport).getAllByRole('status')).toHaveLength(3)
    expect(screen.queryByText('Notification 4')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss queued 1 notification' }))
    expect(screen.getByText('Notification 4')).toBeInTheDocument()
    expect(within(viewport).getAllByRole('status')).toHaveLength(3)
  })
})
