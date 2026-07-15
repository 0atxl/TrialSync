const removeTrailingSlash = (value: string) => value.replace(/\/$/, '')

export function getApiBaseUrl(rawValue = import.meta.env.VITE_API_BASE_URL): string {
  const value = rawValue?.trim()
  if (!value) {
    throw new Error('VITE_API_BASE_URL is required. Copy .env.example to .env.')
  }

  const isRelative = value.startsWith('/')
  if (!isRelative) {
    const parsed = new URL(value)
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      throw new Error('VITE_API_BASE_URL must be an HTTP(S) URL or a root-relative path.')
    }
  }

  return removeTrailingSlash(value)
}

