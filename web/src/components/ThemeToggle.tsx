import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

import { applyTheme, preferredTheme, storedTheme, THEME_KEY, type Theme } from '../theme'

export function ThemeToggle({ className = '' }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>(preferredTheme)
  const nextTheme = theme === 'dark' ? 'light' : 'dark'

  useEffect(() => { applyTheme(theme) }, [theme])
  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!preference) return
    const followSystem = (event: MediaQueryListEvent) => {
      if (!storedTheme()) setTheme(event.matches ? 'dark' : 'light')
    }
    preference.addEventListener('change', followSystem)
    return () => preference.removeEventListener('change', followSystem)
  }, [])

  const toggle = () => {
    setTheme(nextTheme)
    applyTheme(nextTheme)
    try { localStorage.setItem(THEME_KEY, nextTheme) } catch { /* preference storage is optional */ }
  }

  return <button
    className={`theme-toggle${className ? ` ${className}` : ''}`}
    type="button"
    aria-label={`Switch to ${nextTheme} mode`}
    title={`Switch to ${nextTheme} mode`}
    onClick={toggle}
  >
    {theme === 'dark' ? <Sun aria-hidden="true" size={17} /> : <Moon aria-hidden="true" size={17} />}
  </button>
}
