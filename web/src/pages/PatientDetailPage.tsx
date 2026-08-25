import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  ApiError,
  apiRequest,
  type Fact,
  type Patient,
  type PatientFactCatalog,
  type PatientFactCatalogEntry,
  type PatientFactGroup,
  type PatientUnsupportedDetail,
  type Screening,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import {
  ClinicalDetailEditor,
  type ClinicalDetailSubmission,
  type UnsupportedDetailSubmission,
} from '../components/ClinicalDetailEditor'
import { ConfirmationDialog } from '../components/ConfirmationDialog'
import { PatientActivity } from '../components/PatientActivity'
import {
  PatientClinicalDetailsSection,
  PatientDemographicsSection,
  type DemographicsDraft,
} from '../components/PatientRecordSections'
import { RelatedScreenings } from '../components/RelatedScreenings'
import { UnsavedChangesDialog } from '../components/UnsavedChangesDialog'
import { TechnicalDetails } from '../components/UiPrimitives'
import { useToast } from '../components/ToastProvider'
import { useMutationState } from '../hooks/useMutationState'
import { useUnsavedChanges } from '../hooks/useUnsavedChanges'
import { isFutureIsoDate } from '../utils/dates'
import { biologicalSexLabel } from '../utils/demographics'
import { clinicalValueLabel, factCatalogEntry, factLabel } from '../utils/patientFacts'

function displayValue(value: string | null) {
  return value?.trim() || 'Not recorded'
}

function profileChanges(before: Patient, after: Patient) {
  return [
    before.display_name !== after.display_name
      ? `Display name changed from ${before.display_name} to ${after.display_name}.`
      : null,
    before.date_of_birth !== after.date_of_birth
      ? `Date of birth changed from ${displayValue(before.date_of_birth)} to ${displayValue(after.date_of_birth)}.`
      : null,
    before.sex !== after.sex
      ? `Biological sex changed from ${biologicalSexLabel(before.sex)} to ${biologicalSexLabel(after.sex)}.`
      : null,
  ].filter((change): change is string => change !== null)
}

function profileChangeMessage(changes: string[]) {
  if (changes.length === 0) return 'Patient profile saved with no value changes.'
  return changes.length === 1 ? changes[0] : `Patient profile updated with ${changes.length} changes.`
}

export function PatientDetailPage() {
  const { patientId = '' } = useParams()
  const { token, user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [patient, setPatient] = useState<Patient | null>(null)
  const [screenings, setScreenings] = useState<Screening[]>([])
  const [error, setError] = useState('')
  const [editingDemographics, setEditingDemographics] = useState(false)
  const [demographicsDraft, setDemographicsDraft] = useState<DemographicsDraft | null>(null)
  const [profileError, setProfileError] = useState('')
  const [profileStale, setProfileStale] = useState(false)
  const [profileConflictFactId, setProfileConflictFactId] = useState<string | null>(null)
  const [savedProfileChanges, setSavedProfileChanges] = useState<string[]>([])
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deletingFactId, setDeletingFactId] = useState<string | null>(null)
  const [factToVoid, setFactToVoid] = useState<Fact | null>(null)
  const [voidReason, setVoidReason] = useState('')
  const [voidReasonError, setVoidReasonError] = useState('')
  const [catalog, setCatalog] = useState<PatientFactCatalogEntry[]>([])
  const [catalogError, setCatalogError] = useState('')
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [detailQuery, setDetailQuery] = useState('')
  const [detailEditorOpen, setDetailEditorOpen] = useState(false)
  const [editingFact, setEditingFact] = useState<Fact | null>(null)
  const [detailError, setDetailError] = useState('')
  const [detailNotice, setDetailNotice] = useState('')
  const profileMutation = useMutationState()
  const factMutation = useMutationState()
  const resetProfileMutation = profileMutation.reset
  const unsavedChanges = useUnsavedChanges(
    profileMutation.hasUnsavedChanges || factMutation.hasUnsavedChanges,
  )

  const load = useCallback(async () => {
    try {
      const [record, activity, savedScreenings] = await Promise.all([
        apiRequest<Patient>(`/patients/${patientId}`, {}, token),
        apiRequest<unknown>(`/patients/${patientId}/activity`, {}, token),
        apiRequest<Screening[]>(`/screenings?patient_id=${encodeURIComponent(patientId)}`, {}, token)
          .catch(() => []),
      ])
      setPatient({ ...record, activity: Array.isArray(activity) ? activity : [] })
      setScreenings(Array.isArray(savedScreenings) ? savedScreenings : [])
      setError('')
      setProfileError('')
      setProfileStale(false)
      setProfileConflictFactId(null)
      setEditingDemographics(false)
      setDemographicsDraft(null)
      resetProfileMutation()
    } catch {
      setError('Patient record could not be loaded.')
    }
  }, [patientId, resetProfileMutation, token])

  useEffect(() => {
    void load()
  }, [load])

  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true)
    try {
      const response = await apiRequest<PatientFactCatalog>(
        '/patient-fact-catalog',
        {},
        token,
      )
      if (!Array.isArray(response.entries)) {
        throw new Error('Catalog response did not contain entries.')
      }
      setCatalog(response.entries)
      setCatalogError('')
    } catch {
      setCatalogError('Supported clinical details could not be loaded.')
    } finally {
      setCatalogLoading(false)
    }
  }, [token])

  const loadActivity = useCallback(async () => {
    if (!patientId) return
    try {
      const activity = await apiRequest<unknown>(
        `/patients/${patientId}/activity`,
        {},
        token,
      )
      if (Array.isArray(activity)) {
        setPatient((current) => current ? { ...current, activity } : current)
      }
    } catch {
      // Activity is supplementary to the patient record and must not block editing.
    }
  }, [patientId, token])

  useEffect(() => {
    void loadCatalog()
  }, [loadCatalog])

  const beginDemographicsEdit = () => {
    if (!patient) return
    setDemographicsDraft({
      display_name: patient.display_name,
      date_of_birth: patient.date_of_birth ?? '',
      sex: patient.sex,
    })
    setProfileError('')
    setProfileStale(false)
    setProfileConflictFactId(null)
    setSavedProfileChanges([])
    profileMutation.reset()
    setEditingDemographics(true)
  }

  const updateDemographics = <Key extends keyof DemographicsDraft>(
    key: Key,
    value: DemographicsDraft[Key],
  ) => {
    if (!patient) return
    setDemographicsDraft((current) => {
      if (!current) return current
      const updated = { ...current, [key]: value }
      profileMutation.setDirty(
        updated.display_name !== patient.display_name ||
          (updated.date_of_birth || null) !== patient.date_of_birth ||
          updated.sex !== patient.sex,
      )
      return updated
    })
    setProfileError('')
    setProfileStale(false)
    setProfileConflictFactId(null)
  }

  const cancelDemographicsEdit = () => {
    setEditingDemographics(false)
    setDemographicsDraft(null)
    setProfileError('')
    setProfileStale(false)
    setProfileConflictFactId(null)
    profileMutation.reset()
  }

  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!patient || !demographicsDraft) return
    if (isFutureIsoDate(demographicsDraft.date_of_birth)) {
      setProfileError('Date of birth cannot be in the future.')
      return
    }
    if (!profileMutation.start()) return
    const previous = patient
    setProfileError('')
    setProfileStale(false)
    try {
      const updated = await apiRequest<Patient>(
        `/patients/${patientId}`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            display_name: demographicsDraft.display_name,
            date_of_birth: demographicsDraft.date_of_birth || null,
            sex: demographicsDraft.sex,
            expected_updated_at: patient.updated_at,
          }),
        },
        token,
      )
      const changes = profileChanges(previous, updated)
      showToast({
        variant: 'success',
        title: 'Profile saved',
        message: profileChangeMessage(changes),
      })
      setPatient(updated)
      void loadActivity()
      setSavedProfileChanges(changes)
      setProfileConflictFactId(null)
      setEditingDemographics(false)
      setDemographicsDraft(null)
      profileMutation.succeed()
    } catch (exception) {
      const stale =
        exception instanceof ApiError && exception.code === 'PATIENT_RECORD_STALE'
      const pregnancyConflict =
        exception instanceof ApiError &&
        exception.code === 'PATIENT_PREGNANCY_SEX_CONFLICT'
      const conflictFactId = pregnancyConflict
        ? String(exception.details?.[0]?.fact_id ?? '')
        : ''
      const message = stale
        ? 'This profile changed in another session. Reload the latest values before saving.'
        : pregnancyConflict
          ? 'Biological sex cannot be changed to Male while Pregnancy status is Pregnant. Review pregnancy status first.'
        : exception instanceof ApiError && exception.code === 'PATIENT_DOB_IN_FUTURE'
          ? 'Date of birth cannot be in the future.'
          : 'Patient profile could not be updated. Your entered values are still here.'
      profileMutation.fail()
      setProfileStale(stale)
      setProfileConflictFactId(conflictFactId || null)
      setProfileError(message)
      showToast({ variant: 'error', title: 'Profile not saved', message, announce: false })
    }
  }

  const openAddDetail = () => {
    setEditingFact(null)
    setDetailError('')
    setDetailNotice('')
    factMutation.reset()
    setDetailEditorOpen(true)
  }

  const openEditDetail = (fact: Fact, notice = '') => {
    setEditingFact(fact)
    setDetailError('')
    setDetailNotice(notice)
    factMutation.reset()
    setDetailEditorOpen(true)
  }

  const closeDetailEditor = () => {
    setDetailEditorOpen(false)
    setEditingFact(null)
    setDetailError('')
    setDetailNotice('')
    factMutation.reset()
  }

  const reloadFromDetailEditor = () => {
    closeDetailEditor()
    void load()
  }

  const reviewPregnancyConflict = (factId: string) => {
    const fact = patient?.facts.find((item) => item.id === factId)
    if (!fact) {
      void load()
      return
    }
    cancelDemographicsEdit()
    openEditDetail(
      fact,
      'Review Pregnancy status before changing biological sex to Male. No value was changed automatically.',
    )
  }

  const saveClinicalDetail = async ({
    catalogKey,
    value,
  }: ClinicalDetailSubmission) => {
    if (!patient || !factMutation.start()) return
    const previous = editingFact
    const entry = catalog.find((item) => item.key === catalogKey)
    if (!entry) {
      factMutation.fail()
      setDetailError('This clinical detail is no longer available. Reload the catalog.')
      return
    }
    setDetailError('')
    setDetailNotice('')
    try {
      const saved = previous
        ? await apiRequest<Fact>(
            `/patients/${patientId}/facts/${previous.id}`,
            {
              method: 'PATCH',
              body: JSON.stringify({
                value,
                expected_fact_updated_at: previous.updated_at,
              }),
            },
            token,
          )
        : await apiRequest<Fact>(
            `/patients/${patientId}/facts`,
            {
              method: 'POST',
              body: JSON.stringify({
                catalog_key: catalogKey,
                value,
                expected_patient_updated_at: patient.updated_at,
              }),
            },
            token,
          )
      setPatient((current) => {
        if (!current) return current
        return {
          ...current,
          facts: previous
            ? current.facts.map((item) => item.id === saved.id ? saved : item)
          : [...current.facts, saved],
        }
      })
      void loadActivity()
      factMutation.succeed()
      setDetailEditorOpen(false)
      setEditingFact(null)
      const savedValue = clinicalValueLabel(saved, entry)
      showToast({
        variant: 'success',
        title: previous ? 'Clinical detail updated' : 'Clinical detail added',
        message: previous
          ? `${entry.display_label} changed from ${clinicalValueLabel(previous, entry)} to ${savedValue}.`
          : `${entry.display_label} added: ${savedValue}.`,
      })
    } catch (exception) {
      if (exception instanceof ApiError && exception.code === 'PATIENT_FACT_DUPLICATE') {
        const duplicateId = String(exception.details?.[0]?.fact_id ?? '')
        const duplicate = patient.facts.find((fact) => fact.id === duplicateId)
        if (duplicate) {
          openEditDetail(
            duplicate,
            `${entry.display_label} already exists. You are now editing the current detail.`,
          )
          showToast({
            variant: 'information',
            title: 'Existing detail opened',
            message: `${entry.display_label} is already recorded. Review and edit it here.`,
          })
          return
        }
      }
      const message =
        exception instanceof ApiError && exception.code === 'PATIENT_RECORD_STALE'
          ? 'This clinical detail changed after you opened it. Reload before saving.'
          : exception instanceof ApiError &&
              exception.code === 'PATIENT_PREGNANCY_SEX_CONFLICT'
            ? 'Pregnancy cannot be changed to Pregnant while biological sex is Male. Review the demographic profile or choose another explicit status.'
          : 'The clinical detail could not be saved. Your entered values are still here.'
      factMutation.fail()
      setDetailError(message)
      showToast({
        variant: 'error',
        title: 'Clinical detail not saved',
        message,
        announce: false,
      })
    }
  }

  const saveUnsupportedDetail = async ({
    category,
    label,
    context,
  }: UnsupportedDetailSubmission) => {
    if (!patient || !factMutation.start()) return
    setDetailError('')
    try {
      const saved = await apiRequest<PatientUnsupportedDetail>(
        `/patients/${patientId}/unsupported-details`,
        {
          method: 'POST',
          body: JSON.stringify({ category, label, context }),
        },
        token,
      )
      setPatient((current) => current
        ? {
            ...current,
            unsupported_details: [...(current.unsupported_details ?? []), saved],
          }
        : current)
      factMutation.succeed()
      setDetailEditorOpen(false)
      showToast({
        variant: 'information',
        title: 'Review item recorded',
        message: `${saved.label} is visible on this record but is not used for screening.`,
      })
    } catch (exception) {
      const message =
        exception instanceof ApiError &&
        exception.code === 'PATIENT_UNSUPPORTED_DETAIL_DUPLICATE'
          ? 'This unsupported detail is already recorded for review.'
          : 'The review item could not be saved. Your entered values are still here.'
      factMutation.fail()
      setDetailError(message)
      showToast({
        variant: 'error',
        title: 'Review item not saved',
        message,
        announce: false,
      })
    }
  }

  const requestVoidFact = (fact: Fact) => {
    setFactToVoid(fact)
    setVoidReason('')
    setVoidReasonError('')
    setError('')
  }

  const restoreFact = async (factId: string, label: string) => {
    setDeletingFactId(factId)
    try {
      await apiRequest<Fact>(
        `/patients/${patientId}/facts/${factId}/restore`,
        { method: 'POST' },
        token,
      )
      await load()
      await loadActivity()
      showToast({
        variant: 'success',
        title: 'Clinical detail restored',
        message: `${label} is active again for future screenings.`,
      })
    } catch (exception) {
      const message =
        exception instanceof ApiError && exception.code === 'PATIENT_FACT_RESTORE_CONFLICT'
          ? 'This detail could not be restored because an active copy already exists.'
          : `${label} could not be restored. No changes were made.`
      setError(message)
      showToast({
        variant: 'error',
        title: 'Clinical detail not restored',
        message,
        announce: false,
      })
    } finally {
      setDeletingFactId(null)
    }
  }

  const voidFact = async () => {
    const fact = factToVoid
    if (!fact) return
    const reason = voidReason.trim()
    if (!reason) {
      setVoidReasonError('Add a short reason so the record history explains this removal.')
      return
    }
    const label = factCatalogEntry(catalog, fact)?.display_label ?? factLabel(fact)
    setDeletingFactId(fact.id)
    setVoidReasonError('')
    setError('')
    try {
      await apiRequest(
        `/patients/${patientId}/facts/${fact.id}`,
        {
          method: 'DELETE',
          body: JSON.stringify({ reason, expected_fact_updated_at: fact.updated_at }),
        },
        token,
      )
      setFactToVoid(null)
      setVoidReason('')
      await load()
      await loadActivity()
      showToast({
        variant: 'success',
        title: 'Clinical detail removed',
        message: `${label} was removed. Existing saved screenings are unchanged.`,
        action: {
          label: 'Undo',
          onClick: () => { void restoreFact(fact.id, label) },
        },
      })
    } catch (exception) {
      const message =
        exception instanceof ApiError && exception.code === 'PATIENT_RECORD_STALE'
          ? `${label} changed after you opened it. Reload the latest record before removing.`
          : `${label} could not be removed. No changes were made.`
      setError(message)
      showToast({
        variant: 'error',
        title: 'Clinical detail not removed',
        message,
        announce: false,
      })
    } finally {
      setDeletingFactId(null)
    }
  }

  const deleteUnsupportedDetail = async (detail: PatientUnsupportedDetail) => {
    setDeletingFactId(detail.id)
    try {
      await apiRequest(
        `/patients/${patientId}/unsupported-details/${detail.id}`,
        { method: 'DELETE' },
        token,
      )
      setPatient((current) => current
        ? {
            ...current,
            unsupported_details: (current.unsupported_details ?? [])
              .filter((item) => item.id !== detail.id),
          }
        : current)
      showToast({
        variant: 'success',
        title: 'Review item removed',
        message: `${detail.label} was removed from the unsupported-detail review list.`,
      })
    } catch {
      showToast({
        variant: 'error',
        title: 'Review item not removed',
        message: `${detail.label} could not be removed. No changes were made.`,
      })
    } finally {
      setDeletingFactId(null)
    }
  }

  const deletePatient = async () => {
    if (!patient) return
    const patientName = patient.display_name
    setDeleting(true)
    try {
      await apiRequest(`/patients/${patientId}`, { method: 'DELETE' }, token)
      showToast({
        variant: 'success',
        title: 'Patient removed',
        message: `${patientName} was removed from the active workspace. Saved screenings are unchanged.`,
      })
      unsavedChanges.allowNextNavigation()
      navigate('/patients', { replace: true })
    } catch {
      setDeleteOpen(false)
      const message = 'Patient record could not be deleted. No changes were made.'
      setError(message)
      showToast({ variant: 'error', title: 'Patient not removed', message, announce: false })
    } finally {
      setDeleting(false)
    }
  }

  const groupedFacts = useMemo<Record<PatientFactGroup, Fact[]>>(() => {
    const result: Record<PatientFactGroup, Fact[]> = {
      conditions: [],
      medications: [],
      observations: [],
    }
    const term = detailQuery.trim().toLowerCase()
    for (const fact of patient?.facts ?? []) {
      const entry = factCatalogEntry(catalog, fact)
      const label = entry?.display_label ?? factLabel(fact)
      if (
        term &&
        !`${label} ${fact.concept} ${clinicalValueLabel(fact, entry)}`
          .toLowerCase()
          .includes(term)
      ) continue
      const group: PatientFactGroup =
        entry?.group ??
        (fact.fact_type === 'medication'
          ? 'medications'
          : fact.fact_type === 'observation'
            ? 'observations'
            : 'conditions')
      result[group].push(fact)
    }
    for (const group of Object.keys(result) as PatientFactGroup[]) {
      result[group].sort((left, right) => {
        if (group === 'observations') {
          return (right.effective_date ?? '').localeCompare(left.effective_date ?? '')
        }
        const leftOrder = factCatalogEntry(catalog, left)?.display_order ?? 999
        const rightOrder = factCatalogEntry(catalog, right)?.display_order ?? 999
        return leftOrder - rightOrder
      })
    }
    return result
  }, [catalog, detailQuery, patient?.facts])

  if (error && !patient) return <div className="form-error" role="alert">{error}</div>
  if (!patient) return <div className="loading-state">Loading patient record…</div>
  const pregnancyPresent = patient.facts.find(
    (fact) =>
      fact.fact_type === 'condition' &&
      fact.concept === 'pregnancy' &&
      fact.assertion === 'present',
  )
  const pregnancySexConflict =
    patient.sex === 'male' ? pregnancyPresent : undefined
  const pregnancySexWarning =
    patient.sex === null ? pregnancyPresent : undefined

  return (
    <section className="route-entry workspace-page">
      <Link className="back-link" to="/patients">← Patients</Link>
      <header className="page-heading">
        <h1>{patient.display_name}</h1>
        <div className="page-actions">
          <Link
            className="primary-button"
            to={`/screenings/new?patient_id=${encodeURIComponent(patient.id)}`}
          >
            New screening
          </Link>
          <button
            className="danger-button danger-button-subtle"
            type="button"
            onClick={() => setDeleteOpen(true)}
          >
            Delete patient
          </button>
        </div>
      </header>
      <PatientDemographicsSection
        patient={patient}
        draft={demographicsDraft}
        editing={editingDemographics}
        error={profileError}
        stale={profileStale}
        conflictFactId={profileConflictFactId}
        savedChanges={savedProfileChanges}
        saving={profileMutation.isSaving}
        dirty={profileMutation.hasUnsavedChanges}
        onBeginEdit={beginDemographicsEdit}
        onCancel={cancelDemographicsEdit}
        onReload={() => { void load() }}
        onReviewConflict={reviewPregnancyConflict}
        onSubmit={saveProfile}
        onUpdate={updateDemographics}
      />
      {pregnancySexConflict ? (
        <section
          className="patient-consistency-panel consistency-conflict"
          aria-labelledby="pregnancy-conflict-heading"
          role="alert"
        >
          <div>
            <p className="eyebrow">Data consistency needs review</p>
            <h2 id="pregnancy-conflict-heading">Reconcile biological sex and pregnancy</h2>
            <p>
              Biological sex is Male while pregnancy is recorded as Pregnant. Review
              either value before using this record in a new screening.
            </p>
          </div>
          <div className="patient-consistency-actions">
            <button
              className="primary-button"
              type="button"
              onClick={() => reviewPregnancyConflict(pregnancySexConflict.id)}
            >
              Review pregnancy status
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={beginDemographicsEdit}
            >
              Edit demographics
            </button>
          </div>
        </section>
      ) : pregnancySexWarning ? (
        <section
          className="patient-consistency-panel consistency-warning"
          aria-labelledby="pregnancy-warning-heading"
          role="status"
        >
          <div>
            <p className="eyebrow">Profile completeness</p>
            <h2 id="pregnancy-warning-heading">Biological sex is not recorded</h2>
            <p>
              Pregnancy is recorded as Pregnant. Complete the demographic profile before
              reviewing a new screening.
            </p>
          </div>
          <button
            className="secondary-button"
            type="button"
            onClick={beginDemographicsEdit}
          >
            Complete demographics
          </button>
        </section>
      ) : null}
      {error && <div className="form-error" role="alert">{error}</div>}
      <PatientClinicalDetailsSection
        patient={patient}
        catalog={catalog}
        groupedFacts={groupedFacts}
        query={detailQuery}
        catalogLoading={catalogLoading}
        catalogError={catalogError}
        deletingFactId={deletingFactId}
        onAdd={openAddDetail}
        onEdit={openEditDetail}
        onRemove={requestVoidFact}
        onRemoveUnsupported={(detail) => { void deleteUnsupportedDetail(detail) }}
        onQueryChange={setDetailQuery}
        onReloadCatalog={() => { void loadCatalog() }}
      />
      <ClinicalDetailEditor
        open={detailEditorOpen}
        presentation="inline"
        token={token}
        canCreateSupportedTerm={Boolean(user?.is_catalog_admin)}
        entries={catalog}
        fact={editingFact}
        error={detailError}
        notice={detailNotice}
        saving={factMutation.isSaving}
        hasUnsavedChanges={factMutation.hasUnsavedChanges}
        biologicalSex={patient.sex}
        onCancel={closeDetailEditor}
        onDirtyChange={factMutation.setDirty}
        onReload={reloadFromDetailEditor}
        onSubmit={(submission) => void saveClinicalDetail(submission)}
        onSubmitUnsupported={(submission) => void saveUnsupportedDetail(submission)}
        onCatalogEntryCreated={(entry) => setCatalog((current) => [...current, entry])}
      />
      <div className="record-secondary-grid">
        <RelatedScreenings screenings={screenings} counterpart="trial" />
        <PatientActivity events={patient.activity ?? []} />
      </div>
      <TechnicalDetails>
        <dl className="technical-details-list">
          <div><dt>Record reference</dt><dd>{patient.external_id}</dd></div>
          <div><dt>Created</dt><dd>{new Date(patient.created_at).toLocaleString()}</dd></div>
          <div><dt>Last updated</dt><dd>{new Date(patient.updated_at).toLocaleString()}</dd></div>
        </dl>
      </TechnicalDetails>
      <ConfirmationDialog
        open={Boolean(factToVoid)}
        title="Remove this clinical detail?"
        confirmLabel="Remove detail"
        busyLabel="Removing…"
        busy={Boolean(factToVoid && deletingFactId === factToVoid.id)}
        onCancel={() => {
          if (deletingFactId) return
          setFactToVoid(null)
          setVoidReason('')
          setVoidReasonError('')
        }}
        onConfirm={() => void voidFact()}
      >
        <p>
          This detail will be removed from the current record. Its removal remains in
          recent activity, and existing saved screenings stay unchanged.
        </p>
        <label className="void-reason">
          Removal reason
          <textarea
            autoFocus
            rows={3}
            value={voidReason}
            aria-describedby={voidReasonError ? 'void-reason-error' : undefined}
            onChange={(event) => {
              setVoidReason(event.target.value)
              setVoidReasonError('')
            }}
            placeholder="e.g. Entered against the wrong patient"
          />
        </label>
        {voidReasonError ? (
          <p className="form-error" id="void-reason-error" role="alert">{voidReasonError}</p>
        ) : null}
      </ConfirmationDialog>
      <ConfirmationDialog open={deleteOpen} title="Delete this patient?" confirmLabel="Delete patient" busyLabel="Deleting…" busy={deleting} onCancel={() => setDeleteOpen(false)} onConfirm={() => void deletePatient()}>
        <p><strong>{patient.display_name}</strong> will be removed from Patients. Existing saved screenings will remain available.</p>
      </ConfirmationDialog>
      <UnsavedChangesDialog control={unsavedChanges} />
    </section>
  )
}
