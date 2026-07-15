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
export type ScreeningState = 'potentially_eligible' | 'likely_ineligible' | 'needs_review'
export type ScreeningCounts = { pass_count: number; fail_count: number; unknown_count: number }
export type Evidence = {
  fact_id: string
  source_label?: string
  value?: string | number | null
  unit?: string | null
  effective_date?: string | null
}
export type MissingInformation = { fact: string; reason: string; detail: string }
export type SnapshotSummary = {
  id: string
  external_id: string
  display_name: string
  date_of_birth: string | null
  sex: string | null
  facts: Fact[]
}
export type TrialSummary = { registry_id: string; title: string; version: number }
export type CriterionEvaluation = {
  id: string
  criterion_id: string
  criterion_order: number
  criterion_kind: 'inclusion' | 'exclusion'
  result: 'pass' | 'fail' | 'unknown'
  truth: string
  reason_code: string
  criterion_source_text: string
  canonical_explanation: string
  evidence: Evidence[]
  rejected_evidence: Evidence[]
  missing_information: MissingInformation[]
}
export type Screening = {
  id: string
  batch_id: string | null
  patient_snapshot_id: string
  patient_snapshot: SnapshotSummary
  trial_version_id: string
  trial_version: TrialSummary
  overall_state: ScreeningState
  screening_date: string
  engine_version: string
  dsl_version: string
  terminology_version: string
  unit_version: string
  created_at: string
  counts: ScreeningCounts
  evaluations: CriterionEvaluation[]
}
export type BatchPair = {
  patient_snapshot_id: string
  patient_snapshot: SnapshotSummary
  trial_version_id: string
  trial_version: TrialSummary
  screening_id: string
  overall_state: ScreeningState
  counts: ScreeningCounts
}
export type ScreeningBatch = {
  id: string
  label: string | null
  pair_count: number
  created_at: string
  state_counts: Record<ScreeningState, number>
  unknown_criterion_count: number
  screenings: BatchPair[]
}

export type ImportSource = {
  span_id: string | null
  page: number
  start: number
  end: number
  text: string
}
export type PatientImportFact = {
  candidate_id: string
  selected: boolean
  fact_type: Fact['fact_type']
  concept: string
  value_numeric: string | null
  value_text: string | null
  unit: string | null
  assertion: Fact['assertion']
  effective_date: string | null
  source: ImportSource
  warnings: string[]
}
export type TrialImportCriterion = {
  candidate_id: string
  selected: boolean
  kind: Criterion['kind']
  order: number
  source_text: string
  normalized_rule: Record<string, unknown> | null
  parse_state: 'parsed' | 'needs_manual_rule'
  source: ImportSource
  warnings: string[]
}
export type ImportDocument = {
  id: string
  kind: 'patient' | 'trial'
  source_type: 'text' | 'pdf'
  status: 'needs_review' | 'approved' | 'rejected'
  filename: string | null
  mime_type: string
  size_bytes: number
  checksum: string
  source_text: string
  pages: Array<{ page: number; start_offset: number; end_offset: number; text: string }>
  candidates: {
    profile: Record<string, string | null>
    facts?: PatientImportFact[]
    criteria?: TrialImportCriterion[]
  }
  warnings: string[]
  quality: Record<string, string | number>
  approved_resource_id: string | null
  created_at: string
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details?: Array<Record<string, unknown>>,
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
      body?.error?.details,
    )
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
