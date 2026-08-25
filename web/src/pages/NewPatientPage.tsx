import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import {
  ApiError,
  apiRequest,
  type BiologicalSex,
  type Patient,
  type PatientFactCatalog,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { BiologicalSexField } from '../components/BiologicalSexField'
import {
  ClinicalDetailComposer,
  type ClinicalDetailDraft,
  type UnsupportedClinicalDraft,
} from '../components/ClinicalDetailComposer'
import { ConfirmationDialog } from '../components/ConfirmationDialog'
import {
  DocumentImportStep,
  IngestionPage,
  SourceChoice,
  type IngestionSource,
} from '../components/IngestionFlow'
import { useToast } from '../components/ToastProvider'
import { UnsavedChangesDialog } from '../components/UnsavedChangesDialog'
import { useMutationState } from '../hooks/useMutationState'
import { useUnsavedChanges } from '../hooks/useUnsavedChanges'
import { isFutureIsoDate, todayIsoDate } from '../utils/dates'

type PatientValues = {
  display_name: string
  date_of_birth: string
  sex: BiologicalSex | null
}

const EMPTY_PATIENT: PatientValues = { display_name: '', date_of_birth: '', sex: null }
const steps = [
  { id: 'source', label: 'Source' },
  { id: 'basics', label: 'Basics' },
  { id: 'details', label: 'Clinical details' },
  { id: 'review', label: 'Review' },
]

export function NewPatientPage() {
  const { token, user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const initialSource = params.get('source') === 'import' ? 'import' : null
  const [source, setSource] = useState<IngestionSource | null>(initialSource)
  const [step, setStep] = useState(0)
  const [values, setValues] = useState(EMPTY_PATIENT)
  const [details, setDetails] = useState<ClinicalDetailDraft[]>([])
  const [unsupported, setUnsupported] = useState<UnsupportedClinicalDraft[]>([])
  const [catalog, setCatalog] = useState<PatientFactCatalog['entries']>([])
  const [catalogError, setCatalogError] = useState('')
  const [error, setError] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [duplicateOpen, setDuplicateOpen] = useState(false)
  const [createdId, setCreatedId] = useState('')
  const mutation = useMutationState()
  const dirty = Boolean(values.display_name.trim() || values.date_of_birth || values.sex || details.length || unsupported.length)
  const unsavedChanges = useUnsavedChanges(dirty && !mutation.isSaving)

  const loadCatalog = useCallback(async () => {
    try {
      const response = await apiRequest<PatientFactCatalog>('/patient-fact-catalog', {}, token)
      setCatalog(response.entries)
      setCatalogError('')
    } catch {
      setCatalogError('Clinical details could not be loaded. You can return to Basics or try again.')
    }
  }, [token])

  useEffect(() => {
    if (source === 'manual') void loadCatalog()
  }, [loadCatalog, source])

  const chooseSource = (next: IngestionSource) => {
    setSource(next)
    setParams(next === 'import' ? { source: 'import' } : {}, { replace: true })
    if (next === 'manual') setStep(1)
  }

  const updateValue = <Key extends keyof PatientValues>(key: Key, value: PatientValues[Key]) => {
    setValues((current) => ({ ...current, [key]: value }))
    setFieldError('')
    setError('')
  }

  const continueFromBasics = () => {
    if (!values.display_name.trim()) { setFieldError('Enter a patient name.'); return }
    if (isFutureIsoDate(values.date_of_birth)) { setFieldError('Date of birth cannot be in the future.'); return }
    setFieldError('')
    setStep(2)
  }

  const save = async (confirmDuplicate = false) => {
    if (!mutation.start()) return
    setError('')
    setCreatedId('')
    let savedPatientId = ''
    try {
      let patient = await apiRequest<Patient>('/patients', {
        method: 'POST',
        body: JSON.stringify({
          display_name: values.display_name.trim(),
          date_of_birth: values.date_of_birth || null,
          sex: values.sex,
          confirm_duplicate_name: confirmDuplicate,
        }),
      }, token)
      savedPatientId = patient.id
      setCreatedId(patient.id)
      for (const detail of details) {
        await apiRequest(`/patients/${patient.id}/facts`, {
          method: 'POST',
          body: JSON.stringify({
            catalog_key: detail.catalogKey,
            value: detail.value,
            source_label: 'Manual entry',
            expected_patient_updated_at: patient.updated_at,
          }),
        }, token)
        patient = await apiRequest<Patient>(`/patients/${patient.id}`, {}, token)
      }
      for (const detail of unsupported) {
        await apiRequest(`/patients/${patient.id}/unsupported-details`, {
          method: 'POST',
          body: JSON.stringify({ category: detail.category, label: detail.label, context: detail.context }),
        }, token)
      }
      mutation.succeed()
      unsavedChanges.allowNextNavigation()
      showToast({ variant: 'success', title: 'Patient added', message: `${patient.display_name} is ready to use.` })
      navigate(`/patients/${patient.id}`)
    } catch (exception) {
      mutation.fail()
      if (exception instanceof ApiError && exception.code === 'PATIENT_NAME_REVIEW_REQUIRED') {
        setDuplicateOpen(true)
        setError('A patient with this name already exists.')
      } else if (exception instanceof ApiError && exception.code === 'PATIENT_DOB_IN_FUTURE') {
        setStep(1)
        setFieldError('Date of birth cannot be in the future.')
      } else if (savedPatientId) {
        setError('The patient profile was created, but one or more clinical details still need review. Open the record to finish safely.')
      } else {
        setError('The patient could not be saved. Your entered details are still here.')
      }
    }
  }

  return (
    <IngestionPage title="Add patient" back={{ label: 'Patients', to: '/patients' }} steps={steps} currentStep={step} onStep={source === 'manual' ? (nextStep) => { if (nextStep === 0) { setSource(null); setStep(0) } else setStep(nextStep) } : undefined}>
      {!source ? <SourceChoice entity="patient" onSelect={chooseSource} /> : source === 'import' ? (
        <DocumentImportStep entity="patient" token={token} onBack={() => { setSource(null); setParams({}, { replace: true }) }} onImported={(review) => navigate(`/imports/${review.id}`)} />
      ) : step === 1 ? (
        <section aria-labelledby="patient-basics-title">
          <div className="ingestion-stage-heading"><h2 id="patient-basics-title">Patient profile</h2></div>
          <div className="ingestion-form-grid">
            <label>Display name<input autoFocus name="display_name" value={values.display_name} onChange={(event) => updateValue('display_name', event.target.value)} /></label>
            <label>Date of birth<input max={todayIsoDate()} name="date_of_birth" type="date" value={values.date_of_birth} onChange={(event) => updateValue('date_of_birth', event.target.value)} /></label>
            <BiologicalSexField value={values.sex} onChange={(value) => updateValue('sex', value)} />
          </div>
          {fieldError ? <div className="form-error" role="alert">{fieldError}</div> : null}
          <div className="form-actions ingestion-actions"><button className="secondary-button" type="button" onClick={() => { setSource(null); setStep(0) }}>Back</button><button className="primary-button" type="button" onClick={continueFromBasics}>Continue</button></div>
        </section>
      ) : step === 2 ? (
        <section aria-labelledby="patient-details-title">
          <div className="ingestion-stage-heading"><h2 id="patient-details-title">Clinical details</h2></div>
          {catalogError ? <div className="form-error" role="alert">{catalogError}<button className="text-button" type="button" onClick={() => void loadCatalog()}>Retry</button></div> : <ClinicalDetailComposer entries={catalog} token={token} canCreateSupportedTerm={Boolean(user?.is_catalog_admin)} biologicalSex={values.sex} details={details} unsupported={unsupported} onDetailsChange={setDetails} onUnsupportedChange={setUnsupported} onCatalogEntryCreated={(entry) => setCatalog((current) => [...current, entry])} />}
          <div className="form-actions ingestion-actions"><button className="secondary-button" type="button" onClick={() => setStep(1)}>Back</button><button className="primary-button" disabled={Boolean(catalogError)} type="button" onClick={() => setStep(3)}>Review patient</button></div>
        </section>
      ) : (
        <section aria-labelledby="patient-review-title">
          <div className="ingestion-stage-heading"><h2 id="patient-review-title">Check before saving</h2></div>
          <div className="ingestion-review">
            <section><h3>Patient profile</h3><dl><div><dt>Name</dt><dd>{values.display_name}</dd></div><div><dt>Date of birth</dt><dd>{values.date_of_birth || 'Not recorded'}</dd></div><div><dt>Biological sex</dt><dd>{values.sex === 'female' ? 'Female' : values.sex === 'male' ? 'Male' : 'Not recorded'}</dd></div></dl><button className="text-button" type="button" onClick={() => setStep(1)}>Edit basics</button></section>
            <section><h3>Clinical details</h3><p>{details.length} supported detail{details.length === 1 ? '' : 's'} · {unsupported.length} review item{unsupported.length === 1 ? '' : 's'}</p><button className="text-button" type="button" onClick={() => setStep(2)}>Edit clinical details</button></section>
          </div>
          {error ? <div className="form-error" role="alert">{error}{createdId ? <Link className="text-button" to={`/patients/${createdId}`} onClick={unsavedChanges.allowNextNavigation}>Open patient record</Link> : null}</div> : null}
          <div className="form-actions ingestion-actions"><button className="secondary-button" disabled={mutation.isSaving} type="button" onClick={() => setStep(2)}>Back</button><button className="primary-button" disabled={mutation.isSaving} type="button" onClick={() => void save()}>{mutation.isSaving ? 'Saving patient…' : 'Save patient'}</button></div>
        </section>
      )}
      <ConfirmationDialog open={duplicateOpen} eyebrow="Possible duplicate" title="Create a separate patient?" confirmLabel="Create separate patient" busyLabel="Saving…" busy={mutation.isSaving} onCancel={() => setDuplicateOpen(false)} onConfirm={() => { setDuplicateOpen(false); void save(true) }}><p>Review existing records first if this may be the same person.</p></ConfirmationDialog>
      <UnsavedChangesDialog control={unsavedChanges} />
    </IngestionPage>
  )
}
