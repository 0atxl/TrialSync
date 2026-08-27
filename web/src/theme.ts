export type Theme = 'light' | 'dark'

export const THEME_KEY = 'trialsync_theme'

export function storedTheme(): Theme | null {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch { /* preference storage is optional */ }
  return null
}

export function preferredTheme(): Theme {
  const saved = storedTheme()
  if (saved) return saved
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
}
