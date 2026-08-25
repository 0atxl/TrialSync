import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import {
  apiRequest,
  type PatientFactCatalog,
  type Trial,
  type TrialVersion,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import {
  CriterionComposer,
  type CriterionDraft,
  type UnsupportedCriterionDraft,
} from '../components/CriterionComposer'
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

type TrialValues = { title: string; condition: string; phase: string }
const EMPTY_TRIAL: TrialValues = { title: '', condition: '', phase: '' }
const steps = [
  { id: 'source', label: 'Source' },
  { id: 'basics', label: 'Trial basics' },
  { id: 'inclusion', label: 'Inclusion' },
  { id: 'exclusion', label: 'Exclusion' },
  { id: 'review', label: 'Review' },
]

export function NewTrialPage() {
  const { token } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const initialSource = params.get('source') === 'import' ? 'import' : null
  const [source, setSource] = useState<IngestionSource | null>(initialSource)
  const [step, setStep] = useState(0)
  const [values, setValues] = useState(EMPTY_TRIAL)
  const [criteria, setCriteria] = useState<CriterionDraft[]>([])
  const [unsupported, setUnsupported] = useState<UnsupportedCriterionDraft[]>([])
  const [catalog, setCatalog] = useState<PatientFactCatalog['entries']>([])
  const [catalogError, setCatalogError] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [error, setError] = useState('')
  const [createdId, setCreatedId] = useState('')
  const mutation = useMutationState()
  const dirty = Boolean(values.title.trim() || values.condition.trim() || values.phase.trim() || criteria.length || unsupported.length)
  const unsavedChanges = useUnsavedChanges(dirty && !mutation.isSaving)

  const loadCatalog = useCallback(async () => {
    try {
      const response = await apiRequest<PatientFactCatalog>('/patient-fact-catalog', {}, token)
      setCatalog(response.entries)
      setCatalogError('')
    } catch {
      setCatalogError('Supported criteria could not be loaded. Try again before continuing.')
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

  const updateValue = (key: keyof TrialValues, value: string) => {
    setValues((current) => ({ ...current, [key]: value }))
    setFieldError('')
    setError('')
  }

  const continueFromBasics = () => {
    if (!values.title.trim()) { setFieldError('Enter a trial title.'); return }
    if (!values.condition.trim()) { setFieldError('Enter the condition being studied.'); return }
    setFieldError('')
    setStep(2)
  }

  const save = async () => {
    if ((!criteria.length && !unsupported.length) || !mutation.start()) return
    setError('')
    setCreatedId('')
    let savedTrialId = ''
    try {
      const trial = await apiRequest<Trial>('/trials', {
        method: 'POST',
        body: JSON.stringify({ title: values.title.trim(), condition: values.condition.trim(), phase: values.phase.trim() || null }),
      }, token)
      savedTrialId = trial.id
      setCreatedId(trial.id)
      const version = await apiRequest<TrialVersion>(`/trials/${trial.id}/versions`, {
        method: 'POST',
        body: JSON.stringify({ version: 1, status: 'draft', source_text: null }),
      }, token)
      for (const criterion of criteria) {
        await apiRequest(`/trials/${trial.id}/versions/${version.id}/guided-criteria`, {
          method: 'POST',
          body: JSON.stringify({
            kind: criterion.kind,
            subject_key: criterion.subject_key,
            operator: criterion.operator,
            value: criterion.value,
            minimum: criterion.minimum,
            maximum: criterion.maximum,
            biological_sex: criterion.biological_sex,
          }),
        }, token)
      }
      for (const criterion of unsupported) {
        await apiRequest(`/trials/${trial.id}/versions/${version.id}/unsupported-criteria`, {
          method: 'POST',
          body: JSON.stringify({
            kind: criterion.kind,
            category: criterion.category,
            source_text: criterion.source_text,
          }),
        }, token)
      }
      if (!unsupported.length) {
        await apiRequest(`/trials/${trial.id}/versions/${version.id}`, {
          method: 'PUT',
          body: JSON.stringify({ version: version.version, status: 'approved', source_text: null }),
        }, token)
      }
      mutation.succeed()
      unsavedChanges.allowNextNavigation()
      showToast(unsupported.length
        ? { variant: 'success', title: 'Trial saved', message: 'Review the unfinished criteria before using this trial.' }
        : { variant: 'success', title: 'Trial added', message: 'The current protocol is ready for screening.' })
      navigate(`/trials/${trial.id}`)
    } catch {
      mutation.fail()
      setError(savedTrialId
        ? 'The trial profile was created, but its criteria still need review. Open the trial to finish the protocol.'
        : 'The trial could not be saved. Your entered criteria are still here.')
    }
  }

  const inclusion = criteria.filter((item) => item.kind === 'inclusion')
  const exclusion = criteria.filter((item) => item.kind === 'exclusion')
  const unsupportedInclusion = unsupported.filter((item) => item.kind === 'inclusion')
  const unsupportedExclusion = unsupported.filter((item) => item.kind === 'exclusion')
  const replaceKind = (kind: 'inclusion' | 'exclusion', next: CriterionDraft[]) => setCriteria([...criteria.filter((item) => item.kind !== kind), ...next])
  const replaceUnsupportedKind = (kind: 'inclusion' | 'exclusion', next: UnsupportedCriterionDraft[]) => setUnsupported([...unsupported.filter((item) => item.kind !== kind), ...next])

  return (
    <IngestionPage title="Add trial" back={{ label: 'Trials', to: '/trials' }} steps={steps} currentStep={step} onStep={source === 'manual' ? (nextStep) => { if (nextStep === 0) { setSource(null); setStep(0) } else setStep(nextStep) } : undefined}>
      {!source ? <SourceChoice entity="trial" onSelect={chooseSource} /> : source === 'import' ? (
        <DocumentImportStep entity="trial" token={token} onBack={() => { setSource(null); setParams({}, { replace: true }) }} onImported={(review) => navigate(`/imports/${review.id}`)} />
      ) : step === 1 ? (
        <section aria-labelledby="trial-basics-title">
          <div className="ingestion-stage-heading"><h2 id="trial-basics-title">Trial profile</h2></div>
          <div className="ingestion-form-grid"><label>Trial title<input autoFocus value={values.title} onChange={(event) => updateValue('title', event.target.value)} /></label><label>Condition<input value={values.condition} onChange={(event) => updateValue('condition', event.target.value)} /></label><label>Phase<input placeholder="Optional" value={values.phase} onChange={(event) => updateValue('phase', event.target.value)} /></label></div>
          {fieldError ? <div className="form-error" role="alert">{fieldError}</div> : null}
          <div className="form-actions ingestion-actions"><button className="secondary-button" type="button" onClick={() => { setSource(null); setStep(0) }}>Back</button><button className="primary-button" type="button" onClick={continueFromBasics}>Continue</button></div>
        </section>
      ) : step === 2 || step === 3 ? (
        <section aria-labelledby={`${step === 2 ? 'inclusion' : 'exclusion'}-criteria-title`}>
          <div className="ingestion-stage-heading"><h2 id={`${step === 2 ? 'inclusion' : 'exclusion'}-criteria-title`}>{step === 2 ? 'Inclusion criteria' : 'Exclusion criteria'}</h2></div>
          {catalogError ? <div className="form-error" role="alert">{catalogError}<button className="text-button" type="button" onClick={() => void loadCatalog()}>Retry</button></div> : step === 2 ? <CriterionComposer kind="inclusion" entries={catalog} token={token} criteria={inclusion} unsupported={unsupportedInclusion} onCriteriaChange={(next) => replaceKind('inclusion', next)} onUnsupportedChange={(next) => replaceUnsupportedKind('inclusion', next)} /> : <CriterionComposer kind="exclusion" entries={catalog} token={token} criteria={exclusion} unsupported={unsupportedExclusion} onCriteriaChange={(next) => replaceKind('exclusion', next)} onUnsupportedChange={(next) => replaceUnsupportedKind('exclusion', next)} />}
          <div className="form-actions ingestion-actions"><button className="secondary-button" type="button" onClick={() => setStep(step - 1)}>Back</button><button className="primary-button" disabled={Boolean(catalogError)} type="button" onClick={() => setStep(step + 1)}>{step === 2 ? 'Continue to exclusions' : 'Review trial'}</button></div>
        </section>
      ) : (
        <section aria-labelledby="trial-review-title">
          <div className="ingestion-stage-heading"><h2 id="trial-review-title">Check before saving</h2></div>
          <div className="ingestion-review"><section><h3>{values.title}</h3><dl><div><dt>Condition</dt><dd>{values.condition}</dd></div><div><dt>Phase</dt><dd>{values.phase || 'Not recorded'}</dd></div></dl><button className="text-button" type="button" onClick={() => setStep(1)}>Edit trial basics</button></section><section><h3>Criteria</h3><p>{inclusion.length} inclusion · {exclusion.length} exclusion{unsupported.length ? ` · ${unsupported.length} need review` : ''}</p><button className="text-button" type="button" onClick={() => setStep(2)}>Edit criteria</button></section></div>
          {!criteria.length && !unsupported.length ? <div className="form-error" role="alert">Add at least one criterion before saving.</div> : null}
          {unsupported.length ? <div className="review-pending-notice" role="status">{unsupported.length} criterion{unsupported.length === 1 ? '' : 'a'} will stay marked for review. This trial will not be available for screening until they are resolved.</div> : null}
          {error ? <div className="form-error" role="alert">{error}{createdId ? <Link className="text-button" to={`/trials/${createdId}`} onClick={unsavedChanges.allowNextNavigation}>Open trial</Link> : null}</div> : null}
          <div className="form-actions ingestion-actions"><button className="secondary-button" disabled={mutation.isSaving} type="button" onClick={() => setStep(3)}>Back</button><button className="primary-button" disabled={mutation.isSaving || (!criteria.length && !unsupported.length)} type="button" onClick={() => void save()}>{mutation.isSaving ? 'Saving protocol…' : 'Save trial'}</button></div>
        </section>
      )}
      <UnsavedChangesDialog control={unsavedChanges} />
    </IngestionPage>
  )
}
