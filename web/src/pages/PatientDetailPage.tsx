import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  ApiError,
  apiRequest,
  type BiologicalSex,
  type Fact,
  type Patient,
  type PatientFactCatalog,
  type PatientFactCatalogEntry,
  type PatientFactGroup,
  type PatientUnsupportedDetail,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { BiologicalSexField } from '../components/BiologicalSexField'
import {
  ClinicalDetailEditor,
  type ClinicalDetailSubmission,
  type UnsupportedDetailSubmission,
} from '../components/ClinicalDetailEditor'
import { ConfirmationDialog } from '../components/ConfirmationDialog'
import { UnsavedChangesDialog } from '../components/UnsavedChangesDialog'
import { useToast } from '../components/ToastProvider'
import { useMutationState } from '../hooks/useMutationState'
import { useUnsavedChanges } from '../hooks/useUnsavedChanges'
import { isFutureIsoDate, todayIsoDate } from '../utils/dates'
import { biologicalSexLabel } from '../utils/demographics'

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

type DemographicsDraft = {
  display_name: string
  date_of_birth: string
  sex: BiologicalSex | null
}

function factLabel(fact: Fact) {
  return fact.concept
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

const clinicalGroupLabels: Record<PatientFactGroup, string> = {
  conditions: 'Conditions',
  medications: 'Medications',
  observations: 'Labs and observations',
}

function factCatalogEntry(
  entries: PatientFactCatalogEntry[],
  fact: Fact,
) {
  return entries.find(
    (entry) => entry.fact_type === fact.fact_type && entry.concept === fact.concept,
  )
}

function assertionLabel(fact: Fact, entry?: PatientFactCatalogEntry) {
  if (entry?.input_kind === 'pregnancy_status') {
    if (fact.assertion === 'present') return 'Pregnant'
    if (fact.assertion === 'absent') return 'Not pregnant'
    return 'Unknown'
  }
  return fact.assertion.charAt(0).toUpperCase() + fact.assertion.slice(1)
}

function measurementLabel(fact: Fact) {
  if (fact.assertion === 'unknown') return 'Unknown'
  if (fact.value_numeric === null) return assertionLabel(fact)
  const parsedValue = Number(fact.value_numeric)
  const displayValue = Number.isFinite(parsedValue)
    ? String(parsedValue)
    : fact.value_numeric
  const separator = fact.unit === '%' ? '' : ' '
  return `${displayValue}${fact.unit ? `${separator}${fact.unit}` : ''}`
}

function clinicalValueLabel(fact: Fact, entry?: PatientFactCatalogEntry) {
  return entry?.input_kind === 'numeric'
    ? measurementLabel(fact)
    : assertionLabel(fact, entry)
}

export function PatientDetailPage() {
  const { patientId = '' } = useParams()
  const { token } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [patient, setPatient] = useState<Patient | null>(null)
  const [error, setError] = useState('')
  const [editingDemographics, setEditingDemographics] = useState(false)
  const [demographicsDraft, setDemographicsDraft] = useState<DemographicsDraft | null>(null)
  const [profileError, setProfileError] = useState('')
  const [profileStale, setProfileStale] = useState(false)
  const [savedProfileChanges, setSavedProfileChanges] = useState<string[]>([])
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deletingFactId, setDeletingFactId] = useState<string | null>(null)
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
      setPatient(await apiRequest<Patient>(`/patients/${patientId}`, {}, token))
      setError('')
      setProfileError('')
      setProfileStale(false)
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
  }

  const cancelDemographicsEdit = () => {
    setEditingDemographics(false)
    setDemographicsDraft(null)
    setProfileError('')
    setProfileStale(false)
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
      setSavedProfileChanges(changes)
      setEditingDemographics(false)
      setDemographicsDraft(null)
      profileMutation.succeed()
    } catch (exception) {
      const stale =
        exception instanceof ApiError && exception.code === 'PATIENT_RECORD_STALE'
      const message = stale
        ? 'This profile changed in another session. Reload the latest values before saving.'
        : exception instanceof ApiError && exception.code === 'PATIENT_DOB_IN_FUTURE'
          ? 'Date of birth cannot be in the future.'
          : 'Patient profile could not be updated. Your entered values are still here.'
      profileMutation.fail()
      setProfileStale(stale)
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

  const deleteFact = async (fact: Fact) => {
    const label = factCatalogEntry(catalog, fact)?.display_label ?? factLabel(fact)
    setDeletingFactId(fact.id)
    setError('')
    try {
      await apiRequest(`/patients/${patientId}/facts/${fact.id}`, { method: 'DELETE' }, token)
      setPatient((current) =>
        current
          ? { ...current, facts: current.facts.filter((item) => item.id !== fact.id) }
          : current,
      )
      showToast({
        variant: 'success',
        title: 'Clinical detail removed',
        message: `${label} was removed. Existing saved screenings are unchanged.`,
      })
    } catch {
      const message = `${label} could not be removed. No changes were made.`
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

  return (
    <section className="route-entry workspace-page">
      <Link className="back-link" to="/patients">← Patients</Link>
      <header className="page-heading">
        <div><p className="eyebrow">{patient.external_id}</p><h1>{patient.display_name}</h1></div>
        <button className="danger-button danger-button-subtle" type="button" onClick={() => setDeleteOpen(true)}>Delete patient</button>
      </header>
      <section className="demographics-panel" aria-labelledby="demographics-heading">
        <div className="demographics-heading">
          <div>
            <p className="eyebrow">Current record</p>
            <h2 id="demographics-heading">Demographics</h2>
          </div>
          {!editingDemographics ? (
            <button
              className="secondary-button"
              type="button"
              onClick={beginDemographicsEdit}
            >
              Edit demographics
            </button>
          ) : null}
        </div>
        {editingDemographics && demographicsDraft ? (
          <form className="demographics-form" noValidate onSubmit={saveProfile}>
            <div className="demographics-form-grid">
              <label>
                Display name
                <input
                  required
                  value={demographicsDraft.display_name}
                  onChange={(event) =>
                    updateDemographics('display_name', event.target.value)}
                />
              </label>
              <label>
                Date of birth
                <input
                  aria-describedby={profileError ? 'profile-error' : undefined}
                  max={todayIsoDate()}
                  type="date"
                  value={demographicsDraft.date_of_birth}
                  onChange={(event) =>
                    updateDemographics('date_of_birth', event.target.value)}
                />
              </label>
              <BiologicalSexField
                value={demographicsDraft.sex}
                onChange={(value) => updateDemographics('sex', value)}
              />
            </div>
            {profileError ? (
              <div className="form-error demographics-error" id="profile-error" role="alert">
                <span>{profileError}</span>
                {profileStale ? (
                  <button className="text-button" type="button" onClick={() => void load()}>
                    Reload latest profile
                  </button>
                ) : null}
              </div>
            ) : null}
            <div className="demographics-actions">
              <button
                className="secondary-button"
                disabled={profileMutation.isSaving}
                type="button"
                onClick={cancelDemographicsEdit}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                disabled={profileMutation.isSaving || !profileMutation.hasUnsavedChanges}
                type="submit"
              >
                {profileMutation.isSaving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </form>
        ) : (
          <dl className="demographics-summary">
            <div>
              <dt>Display name</dt>
              <dd>{patient.display_name}</dd>
            </div>
            <div>
              <dt>Date of birth</dt>
              <dd>{displayValue(patient.date_of_birth)}</dd>
            </div>
            <div>
              <dt>Biological sex for screening</dt>
              <dd>{biologicalSexLabel(patient.sex)}</dd>
            </div>
          </dl>
        )}
        {savedProfileChanges.length > 1 ? (
          <div className="change-summary" role="status">
            <strong>Patient profile updated</strong>
            <ul>
              {savedProfileChanges.map((change) => <li key={change}>{change}</li>)}
            </ul>
          </div>
        ) : null}
        <p className="screening-impact-note">
          Existing saved screenings remain unchanged. Future screenings use these current values.
        </p>
      </section>
      {error && <div className="form-error" role="alert">{error}</div>}
      <section className="clinical-details-panel" aria-labelledby="clinical-details-heading">
        <div className="clinical-details-heading">
          <div>
            <p className="eyebrow">Active patient record</p>
            <h2 id="clinical-details-heading">Clinical details</h2>
            <p>Controlled conditions, medications, and dated observations used by screening.</p>
          </div>
          <button
            className="primary-button"
            disabled={catalogLoading || Boolean(catalogError)}
            type="button"
            onClick={openAddDetail}
          >
            {catalogLoading ? 'Loading details…' : 'Add clinical detail'}
          </button>
        </div>
        {catalogError ? (
          <div className="form-error clinical-catalog-error" role="alert">
            <span>{catalogError}</span>
            <button className="text-button" type="button" onClick={() => void loadCatalog()}>
              Try again
            </button>
          </div>
        ) : null}
        <label className="clinical-detail-search">
          <span>Search current details</span>
          <input
            type="search"
            value={detailQuery}
            onChange={(event) => setDetailQuery(event.target.value)}
            placeholder="Search by clinical label or value"
          />
        </label>
        <div className="clinical-detail-groups">
          {(Object.keys(clinicalGroupLabels) as PatientFactGroup[]).map((group) => (
            <section className="clinical-detail-group" key={group}>
              <header>
                <h3>{clinicalGroupLabels[group]}</h3>
                <span>{groupedFacts[group].length}</span>
              </header>
              {groupedFacts[group].length === 0 ? (
                <div className="clinical-group-empty">
                  {detailQuery ? 'No matching details in this group.' : 'No current details.'}
                </div>
              ) : (
                <div className="clinical-detail-rows">
                  {groupedFacts[group].map((fact) => {
                    const entry = factCatalogEntry(catalog, fact)
                    return (
                      <article className="clinical-detail-row" key={fact.id}>
                        <div className="clinical-detail-primary">
                          <strong>{entry?.display_label ?? factLabel(fact)}</strong>
                          <span>{clinicalValueLabel(fact, entry)}</span>
                        </div>
                        <div className="clinical-detail-meta">
                          <span>{fact.effective_date ?? 'Date not recorded'}</span>
                          <small>{fact.source_label}</small>
                        </div>
                        <div className="record-actions">
                          {entry ? (
                            <button
                              className="text-button"
                              type="button"
                              onClick={() => openEditDetail(fact)}
                            >
                              Edit
                            </button>
                          ) : (
                            <span className="unsupported-detail">Review only</span>
                          )}
                          <button
                            className="text-button danger"
                            disabled={deletingFactId === fact.id}
                            onClick={() => void deleteFact(fact)}
                            type="button"
                          >
                            {deletingFactId === fact.id ? 'Removing…' : 'Remove'}
                          </button>
                        </div>
                      </article>
                    )
                  })}
                </div>
              )}
            </section>
          ))}
          <section className="clinical-detail-group unsupported-detail-group">
            <header>
              <h3>Other details — not used for screening</h3>
              <span>{patient.unsupported_details?.length ?? 0}</span>
            </header>
            <p className="unsupported-detail-guidance">
              Retained for catalog review only. These items never become screening
              evidence automatically.
            </p>
            {(patient.unsupported_details?.length ?? 0) === 0 ? (
              <div className="clinical-group-empty">No unsupported details recorded.</div>
            ) : (
              <div className="clinical-detail-rows">
                {patient.unsupported_details.map((detail) => (
                  <article className="clinical-detail-row unsupported-detail-row" key={detail.id}>
                    <div className="clinical-detail-primary">
                      <strong>{detail.label}</strong>
                      <span>{detail.category}</span>
                    </div>
                    <div className="clinical-detail-meta">
                      <span>{detail.context ?? 'No additional context'}</span>
                      <small>{detail.source_label}</small>
                    </div>
                    <div className="record-actions">
                      <span className="unsupported-detail">Review only</span>
                      <button
                        className="text-button danger"
                        disabled={deletingFactId === detail.id}
                        onClick={() => void deleteUnsupportedDetail(detail)}
                        type="button"
                      >
                        {deletingFactId === detail.id ? 'Removing…' : 'Remove'}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </section>
      <ClinicalDetailEditor
        open={detailEditorOpen}
        entries={catalog}
        fact={editingFact}
        error={detailError}
        notice={detailNotice}
        saving={factMutation.isSaving}
        hasUnsavedChanges={factMutation.hasUnsavedChanges}
        onCancel={closeDetailEditor}
        onDirtyChange={factMutation.setDirty}
        onReload={reloadFromDetailEditor}
        onSubmit={(submission) => void saveClinicalDetail(submission)}
        onSubmitUnsupported={(submission) => void saveUnsupportedDetail(submission)}
      />
      <ConfirmationDialog open={deleteOpen} eyebrow="Permanent action" title="Delete this patient?" confirmLabel="Delete patient" busyLabel="Deleting…" busy={deleting} onCancel={() => setDeleteOpen(false)} onConfirm={() => void deletePatient()}>
        <p><strong>{patient.display_name}</strong> will be removed from the active patient workspace. Existing immutable screening snapshots and their evidence history will remain available.</p>
      </ConfirmationDialog>
      <UnsavedChangesDialog control={unsavedChanges} />
    </section>
  )
}
