import { describe, expect, it } from 'vitest'

import { getApiBaseUrl } from '../api/config'

describe('API configuration', () => {
  it('accepts root-relative configuration', () => {
    expect(getApiBaseUrl('/api/v1/')).toBe('/api/v1')
  })

  it('rejects unsupported protocols', () => {
    expect(() => getApiBaseUrl('ftp://example.test/api')).toThrow(/HTTP\(S\)/)
  })
})

