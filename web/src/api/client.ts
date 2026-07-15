import { getApiBaseUrl } from './config'

export type User = { id: string; email: string; display_name: string }
export type AuthResponse = { access_token: string; token_type: string; user: User }
export type Fact = {
  id: string
  fact_type: 'condition' | 'medication' | 'observation' | 'demographic'
  concept: string
  value_numeric: string | null
  value_text: string | null
  unit: string | null
  assertion: 'present' | 'absent' | 'unknown'
  effective_date: string | null
  source_label: string
}
export type Patient = {
  id: string
  external_id: string
  display_name: string
  date_of_birth: string | null
  sex: string | null
  facts: Fact[]
}
export type Criterion = {
  id: string
  kind: 'inclusion' | 'exclusion'
  order: number
  source_text: string
  required: boolean
}
export type TrialVersion = {
  id: string
  version: number
  status: 'draft' | 'approved'
  source_text: string | null
  criteria: Criterion[]
}
export type Trial = {
  id: string
  registry_id: string
  title: string
  condition: string
  phase: string | null
  versions: TrialVersion[]
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message)
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(
      body?.error?.message ?? 'The API request failed.',
      response.status,
      body?.error?.code ?? 'API_ERROR',
    )
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
