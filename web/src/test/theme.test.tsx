import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeToggle } from '../components/ThemeToggle'
import { THEME_KEY } from '../theme'

beforeEach(() => {
  const preferences = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => preferences.get(key) ?? null,
    setItem: (key: string, value: string) => preferences.set(key, value),
    removeItem: (key: string) => preferences.delete(key),
    clear: () => preferences.clear(),
  })
})

afterEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
  document.documentElement.style.colorScheme = ''
  vi.unstubAllGlobals()
})

describe('universal theme toggle', () => {
  it('applies and persists dark mode, then returns to light mode', async () => {
    render(<ThemeToggle />)

    await userEvent.click(screen.getByRole('button', { name: 'Switch to dark mode' }))
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')

    await userEvent.click(screen.getByRole('button', { name: 'Switch to light mode' }))
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
    expect(localStorage.getItem(THEME_KEY)).toBe('light')
  })

  it('follows system changes until the user saves a preference', async () => {
    let listener: ((event: MediaQueryListEvent) => void) | undefined
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: false,
      addEventListener: (_name: string, next: (event: MediaQueryListEvent) => void) => { listener = next },
      removeEventListener: vi.fn(),
    })))

    render(<ThemeToggle />)
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
    act(() => { listener?.({ matches: true } as MediaQueryListEvent) })
    expect(await screen.findByRole('button', { name: 'Switch to light mode' })).toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
  })
})
