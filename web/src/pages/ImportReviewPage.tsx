import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import {
  ApiError,
  apiRequest,
  type ImportDocument,
  type PatientFactCatalog,
  type PatientFactCatalogEntry,
  type PatientImportFact,
  type TrialImportCriterion,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { BiologicalSexField } from '../components/BiologicalSexField'
import { ConfirmationDialog } from '../components/ConfirmationDialog'
import { IngestionPage } from '../components/IngestionFlow'
import {
  FinalImportReview,
  ImportedSource,
  SourceShortcut,
  StepActions,
} from '../components/ImportReviewSections'
import { PatientImportCandidates } from '../components/PatientImportCandidates'
import { TrialImportCandidates } from '../components/TrialImportCandidates'
import { StateMessage } from '../components/UiPrimitives'
import { countUnresolvedCriteria } from '../utils/importCriteria'
import { isFutureIsoDate, todayIsoDate } from '../utils/dates'
import { parseBiologicalSex } from '../utils/demographics'

const patientSteps = [
  { id: 'source', label: 'Source' },
  { id: 'basics', label: 'Basics' },
  { id: 'details', label: 'Clinical details' },
  { id: 'review', label: 'Review' },
]
const trialSteps = [
  { id: 'source', label: 'Source' },
  { id: 'basics', label: 'Trial basics' },
  { id: 'inclusion', label: 'Inclusion' },
  { id: 'exclusion', label: 'Exclusion' },
  { id: 'review', label: 'Review' },
]

export function ImportReviewPage() {
  const { importId = '' } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()
  const [review, setReview] = useState<ImportDocument | null>(null)
  const [catalog, setCatalog] = useState<PatientFactCatalogEntry[]>([])
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [duplicateOpen, setDuplicateOpen] = useState(false)
  const [rejectOpen, setRejectOpen] = useState(false)

  const load = useCallback(async () => {
    try {
      const [loaded, catalogResponse] = await Promise.all([
        apiRequest<ImportDocument>(`/imports/${importId}`, {}, token),
        apiRequest<PatientFactCatalog>('/patient-fact-catalog', {}, token),
      ])
      setReview(loaded)
      setCatalog(catalogResponse.entries)
      setError('')
    } catch {
      setError('The import review could not be loaded.')
    }
  }, [importId, token])
  useEffect(() => { void load() }, [load])

  const back = review?.kind === 'trial' ? '/trials' : '/patients'
  const updateProfile = (key: string, value: string | null) => setReview((current) => current ? ({ ...current, candidates: { ...current.candidates, profile: { ...current.candidates.profile, [key]: value } } }) : current)
  const updateFact = (candidateId: string, values: Partial<PatientImportFact>) => setReview((current) => current ? ({ ...current, candidates: { ...current.candidates, facts: (current.candidates.facts ?? []).map((item) => item.candidate_id === candidateId ? { ...item, ...values } : item) } }) : current)
  const updateCriterion = (candidateId: string, values: Partial<TrialImportCriterion>) => setReview((current) => current ? ({ ...current, candidates: { ...current.candidates, criteria: (current.candidates.criteria ?? []).map((item) => item.candidate_id === candidateId ? { ...item, ...values } : item) } }) : current)

  const reviewedCandidates = () => {
    if (!review) return null
    const candidates = structuredClone(review.candidates)
    if (review.kind === 'patient') {
      const sex = parseBiologicalSex(candidates.profile.sex)
      if (sex !== undefined) candidates.profile.sex = sex
      if (isFutureIsoDate(candidates.profile.date_of_birth ?? '')) throw new Error('Patient date of birth is in the future.')
    }
    return candidates
  }

  const save = async () => {
    const candidates = reviewedCandidates()
    if (!candidates) throw new Error('Review is not loaded.')
    const saved = await apiRequest<ImportDocument>(`/imports/${importId}`, { method: 'PUT', body: JSON.stringify({ candidates }) }, token)
    setReview(saved)
    return saved
  }

  const saveReview = async () => {
    setSaving(true); setError('')
    try { await save() }
    catch (exception) {
      setError(exception instanceof ApiError && exception.code === 'IMPORT_RULE_INVALID'
        ? exception.message
        : exception instanceof Error && exception.message.includes('date of birth')
          ? 'Date of birth cannot be in the future.'
          : 'The review could not be saved. Your changes are still here.')
    } finally { setSaving(false) }
  }

  const approve = async (confirmDuplicate = false) => {
    setSaving(true); setError('')
    try {
      const saved = await save()
      const approval = await apiRequest<{ resource_id: string }>(
        `/imports/${importId}/approve`,
        {
          method: 'POST',
          body: JSON.stringify({ confirm_duplicate_name: confirmDuplicate }),
        },
        token,
      )
      navigate(saved.kind === 'patient'
        ? `/patients/${approval.resource_id}`
        : `/trials/${approval.resource_id}`)
    } catch (exception) {
      if (exception instanceof ApiError && exception.code === 'PATIENT_NAME_REVIEW_REQUIRED') setDuplicateOpen(true)
      else if (exception instanceof ApiError && exception.code === 'IMPORT_REVIEW_INCOMPLETE') {
        setError('Choose a supported criterion or remove every item that still needs review.')
      }
      else if (exception instanceof ApiError && exception.code === 'IMPORT_RULE_INVALID') setError(exception.message)
      else if (exception instanceof Error && exception.message.includes('date of birth')) setError('Date of birth cannot be in the future.')
      else setError('The reviewed import could not be approved. No record was created.')
    } finally { setSaving(false) }
  }

  const reject = async () => {
    setSaving(true)
    try { await apiRequest(`/imports/${importId}`, { method: 'DELETE' }, token); navigate(back) }
    catch { setRejectOpen(false); setError('The import could not be rejected.') }
    finally { setSaving(false) }
  }

  if (error && !review) {
    return <StateMessage state="error" title="Import review unavailable">{error}</StateMessage>
  }
  if (!review) return <StateMessage state="loading" title="Loading import review" />

  const profile = review.candidates.profile
  const patientSex = parseBiologicalSex(profile.sex)
  const patientSexError = review.kind === 'patient' && patientSex === undefined
    ? `“${profile.sex}” is not supported. Choose Female, Male, or Not recorded.`
    : undefined
  const criteria = review.candidates.criteria ?? []
  const unresolved = countUnresolvedCriteria(criteria, catalog)
  const finalStep = review.kind === 'patient' ? 3 : 4
  const steps = review.kind === 'patient' ? patientSteps : trialSteps

  return (
    <IngestionPage
      title={`Review imported ${review.kind}`}
      back={{ label: review.kind === 'patient' ? 'Patients' : 'Trials', to: back }}
      steps={steps}
      currentStep={step}
      onStep={setStep}
    >
      {step === 0 ? (
        <ImportedSource review={review} onContinue={() => setStep(1)} />
      ) : step === 1 ? (
        <section aria-labelledby="import-basics-title">
          <div className="ingestion-stage-heading">
            <h2 id="import-basics-title">{review.kind === 'patient' ? 'Patient profile' : 'Trial profile'}</h2>
          </div>
          <div className="ingestion-form-grid">
            {review.kind === 'patient' ? (
              <>
                <label>
                  Display name
                  <input
                    autoFocus
                    value={profile.display_name ?? ''}
                    onChange={(event) => updateProfile('display_name', event.target.value)}
                  />
                </label>
                <label>
                  Date of birth
                  <input
                    max={todayIsoDate()}
                    type="date"
                    value={profile.date_of_birth ?? ''}
                    onChange={(event) => updateProfile(
                      'date_of_birth', event.target.value || null,
                    )}
                  />
                </label>
                <BiologicalSexField
                  name="import-sex"
                  value={patientSex}
                  invalidMessage={patientSexError}
                  onChange={(value) => updateProfile('sex', value)}
                />
              </>
            ) : (
              <>
                <label>
                  Trial title
                  <input
                    autoFocus
                    value={profile.title ?? ''}
                    onChange={(event) => updateProfile('title', event.target.value)}
                  />
                </label>
                <label>
                  Condition
                  <input
                    value={profile.condition ?? ''}
                    onChange={(event) => updateProfile('condition', event.target.value)}
                  />
                </label>
                <label>
                  Phase
                  <input
                    value={profile.phase ?? ''}
                    onChange={(event) => updateProfile('phase', event.target.value || null)}
                  />
                </label>
              </>
            )}
          </div>
          <SourceShortcut review={review} onOpen={() => setStep(0)} />
          <StepActions back={() => setStep(0)} next={() => setStep(2)} nextLabel="Continue" />
        </section>
      ) : review.kind === 'patient' && step === 2 ? (
        <section aria-labelledby="import-patient-details-title">
          <div className="ingestion-stage-heading">
            <h2 id="import-patient-details-title">Clinical details</h2>
          </div>
          <PatientImportCandidates
            facts={review.candidates.facts ?? []}
            catalog={catalog}
            update={updateFact}
          />
          <SourceShortcut review={review} onOpen={() => setStep(0)} />
          <StepActions back={() => setStep(1)} next={() => setStep(3)} nextLabel="Review patient" />
        </section>
      ) : review.kind === 'trial' && (step === 2 || step === 3) ? (
        <section aria-labelledby="import-trial-criteria-title">
          <div className="ingestion-stage-heading">
            <h2 id="import-trial-criteria-title">
              {step === 2 ? 'Inclusion' : 'Exclusion'} criteria
            </h2>
          </div>
          <TrialImportCandidates
            kind={step === 2 ? 'inclusion' : 'exclusion'}
            criteria={criteria.filter((item) =>
              item.kind === (step === 2 ? 'inclusion' : 'exclusion'),
            )}
            catalog={catalog}
            update={updateCriterion}
          />
          <SourceShortcut review={review} onOpen={() => setStep(0)} />
          <StepActions
            back={() => setStep(step - 1)}
            next={() => setStep(step + 1)}
            nextLabel={step === 2 ? 'Continue to exclusions' : 'Review trial'}
          />
        </section>
      ) : step === finalStep ? (
        <FinalImportReview
          review={review}
          unresolved={unresolved}
          error={error}
          saving={saving}
          onDiscard={() => setRejectOpen(true)}
          onSave={() => void saveReview()}
          onApprove={() => void approve()}
        />
      ) : null}
      <ConfirmationDialog
        open={duplicateOpen}
        eyebrow="Possible duplicate"
        title="Create a separate patient?"
        confirmLabel="Create separate patient"
        busyLabel="Creating…"
        busy={saving}
        onCancel={() => setDuplicateOpen(false)}
        onConfirm={() => { setDuplicateOpen(false); void approve(true) }}
      >
        <p>Review existing records first if this may be the same person.</p>
      </ConfirmationDialog>
      <ConfirmationDialog
        open={rejectOpen}
        eyebrow="Discard import"
        title="Discard this import?"
        confirmLabel="Discard import"
        busyLabel="Discarding…"
        busy={saving}
        onCancel={() => setRejectOpen(false)}
        onConfirm={() => void reject()}
      >
        <p>No patient or trial will be created.</p>
      </ConfirmationDialog>
    </IngestionPage>
  )
}
