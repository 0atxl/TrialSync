import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// React Router's memory history passes jsdom's AbortSignal to Node's undici
// Request implementation. Remove that test-environment-only incompatibility.
const NativeRequest = globalThis.Request
globalThis.Request = class CompatibleRequest extends NativeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    super(input, init ? { ...init, signal: undefined } : init)
  }
}

afterEach(() => {
  cleanup()
})
