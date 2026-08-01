import { getApiBaseUrl } from './config'

export type User = { id: string; email: string; display_name: string; is_catalog_admin: boolean }
export type AuthResponse = { access_token: string; token_type: string; user: User }
export type BiologicalSex = 'male' | 'female'
export type Fact = {
  id: string
  patient_id: string
  fact_type: 'condition' | 'medication' | 'observation' | 'demographic'
  concept: string
  value_numeric: string | null
  value_text: string | null
  unit: string | null
  assertion: 'present' | 'absent' | 'unknown'
  effective_date: string | null
  source_label: string
  created_at: string
  updated_at: string
  voided_at?: string | null
  void_reason?: string | null
}
export type PatientFactGroup = 'conditions' | 'medications' | 'observations'
export type PatientFactInputKind = 'status' | 'pregnancy_status' | 'numeric'
export type PatientFactCatalogEntry = {
  key: string
  fact_type: Fact['fact_type']
  concept: string
  display_label: string
  group: PatientFactGroup
  input_kind: PatientFactInputKind
  allowed_assertions: Fact['assertion'][]
  fixed_unit: string | null
  allowed_units: string[]
  effective_date_required: boolean
  screening_supported: boolean
  help_text: string
  terminology_system: string | null
  terminology_code: string | null
  display_order: number
}
export type TerminologySuggestion = {
  source: 'rxnorm' | 'loinc'
  code: string
  display_label: string
  detail: string | null
  fixed_unit: string | null
  score: number | null
}
export type TerminologySuggestionResponse = {
  query: string
  suggestions: TerminologySuggestion[]
  unavailable_sources: string[]
}
export type PatientFactCatalog = {
  version: string
  entries: PatientFactCatalogEntry[]
}
export type ClinicalConcept = {
  id: string
  key: string
  fact_type: 'condition' | 'medication' | 'observation'
  concept: string
  display_label: string
  concept_group: PatientFactGroup
  input_kind: PatientFactInputKind
  allowed_assertions_json: Fact['assertion'][]
  fixed_unit: string | null
  effective_date_required: boolean
  screening_supported: boolean
  help_text: string
  display_order: number
  active: boolean
  created_at: string
  updated_at: string
}
export type ClinicalDetailValue =
  | {
      input_kind: 'status'
      assertion: Fact['assertion']
      effective_date: string | null
    }
  | {
      input_kind: 'pregnancy_status'
      assertion: Fact['assertion']
      effective_date: string
    }
  | {
      input_kind: 'numeric'
      assertion: 'present' | 'unknown'
      value_numeric: number | null
      effective_date: string
    }
export type PatientUnsupportedDetailCategory =
  | 'condition'
  | 'medication'
  | 'observation'
  | 'other'
export type PatientUnsupportedDetail = {
  id: string
  patient_id: string
  category: PatientUnsupportedDetailCategory
  label: string
  context: string | null
  source_label: string
  created_at: string
  updated_at: string
}
export type PatientConsistencyIssue = {
  code:
    | 'PATIENT_PREGNANCY_SEX_CONFLICT'
    | 'PATIENT_SEX_NOT_RECORDED_FOR_PREGNANCY'
  severity: 'conflict' | 'warning'
  message: string
  field: 'sex' | 'pregnancy'
  fact_id: string
}
export type PatientChangeEvent = {
  id: string
  patient_id: string
  actor_id: string
  event_type: string
  entity_type: string
  entity_id: string | null
  reason: string | null
  before_json: Record<string, unknown> | null
  after_json: Record<string, unknown> | null
  created_at: string
}
export type Patient = {
  id: string
  external_id: string
  display_name: string
  date_of_birth: string | null
  sex: BiologicalSex | null
  created_at: string
  updated_at: string
  facts: Fact[]
  unsupported_details: PatientUnsupportedDetail[]
  consistency_issues: PatientConsistencyIssue[]
  activity?: PatientChangeEvent[]
}
export type Criterion = {
  id: string
  kind: 'inclusion' | 'exclusion'
  order: number
  source_text: string
  normalized_rule: Record<string, unknown> | null
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
  quality: { page_count: number; character_count: number; [key: string]: unknown }
  approved_resource_id: string | null
  created_at: string
}

export type ScreeningChatCitation = {
  criterion_id: string
  evaluation_id: string
  evidence_ids: string[]
  label: string
}
export type ScreeningChatProvider = {
  enabled: boolean
  provider: string
  model: string | null
  prompt_version: string
}
export type ScreeningChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  answer_state: 'supported' | 'insufficient_evidence' | 'refused' | null
  citations: ScreeningChatCitation[]
  provider: ScreeningChatProvider | null
  created_at: string
  suggested_questions: string[]
}
export type ScreeningConversation = {
  screening_id: string
  messages: ScreeningChatMessage[]
  provider: ScreeningChatProvider
  suggested_questions: string[]
  max_messages: number
  max_message_chars: number
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

async function responseError(response: Response, fallback: string): Promise<ApiError> {
  const body = await response.json().catch(() => null)
  return new ApiError(
    body?.error?.message ?? fallback,
    response.status,
    body?.error?.code ?? 'API_ERROR',
    body?.error?.details,
  )
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
    throw await responseError(response, 'The API request failed.')
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function apiDownload(
  path: string,
  token?: string | null,
): Promise<Blob> {
  const headers = new Headers()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${getApiBaseUrl()}${path}`, { headers })
  if (!response.ok) {
    throw await responseError(response, 'The download could not be prepared.')
  }
  return response.blob()
}
