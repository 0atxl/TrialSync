import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  ApiError,
  apiRequest,
  type Criterion,
  type PatientFactCatalog,
  type PatientFactCatalogEntry,
  type Screening,
  type Trial,
  type TrialVersion,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ConfirmationDialog } from '../components/ConfirmationDialog'
import { RelatedScreenings } from '../components/RelatedScreenings'
import { TechnicalDetails } from '../components/UiPrimitives'
import { TrialCriteriaSection } from '../components/TrialCriteriaSection'
import { useToast } from '../components/ToastProvider'
import {
  TrialCriterionEditor,
  type GuidedCriterionSubmission,
  type UnsupportedCriterionSubmission,
} from '../components/TrialCriterionEditor'

type TrialProfileDraft = {
  title: string
  condition: string
  phase: string
}

export function TrialDetailPage() {
  const { trialId = '' } = useParams()
  const { token, user } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [trial, setTrial] = useState<Trial | null>(null)
  const [screenings, setScreenings] = useState<Screening[]>([])
  const [catalog, setCatalog] = useState<PatientFactCatalogEntry[]>([])
  const [catalogError, setCatalogError] = useState('')
  const [error, setError] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [editingProfile, setEditingProfile] = useState(false)
  const [profileDraft, setProfileDraft] = useState<TrialProfileDraft | null>(null)
  const [criterionEditorOpen, setCriterionEditorOpen] = useState(false)
  const [criterionKind, setCriterionKind] = useState<Criterion['kind']>('inclusion')
  const [editingCriterion, setEditingCriterion] = useState<Criterion | null>(null)
  const [criterionError, setCriterionError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [record, savedScreenings] = await Promise.all([
        apiRequest<Trial>(`/trials/${trialId}`, {}, token),
        apiRequest<Screening[]>(`/screenings?trial_id=${encodeURIComponent(trialId)}`, {}, token)
          .catch(() => []),
      ])
      setTrial(record)
      setScreenings(Array.isArray(savedScreenings) ? savedScreenings : [])
      setError('')
    } catch {
      setError('Trial could not be loaded.')
    }
  }, [token, trialId])

  const loadCatalog = useCallback(async () => {
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
      setCatalogError('Supported trial criteria could not be loaded.')
    }
  }, [token])

  useEffect(() => {
    void load()
    void loadCatalog()
  }, [load, loadCatalog])

  const activeDraft = useMemo(
    () => trial?.versions.find((version) => version.status === 'draft') ?? null,
    [trial?.versions],
  )
  const currentProtocol = useMemo(
    () => activeDraft ?? trial?.versions.filter((version) => version.status === 'approved').at(-1) ?? null,
    [activeDraft, trial?.versions],
  )
  const editingCriteria = activeDraft !== null

  const beginProfileEdit = () => {
    if (!trial) return
    setProfileDraft({
      title: trial.title,
      condition: trial.condition,
      phase: trial.phase ?? '',
    })
    setEditingProfile(true)
  }

  const saveTrial = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!profileDraft || saving) return
    setSaving(true)
    try {
      const saved = await apiRequest<Trial>(
        `/trials/${trialId}`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            title: profileDraft.title,
            condition: profileDraft.condition,
            phase: profileDraft.phase || null,
          }),
        },
        token,
      )
      setTrial(saved)
      setEditingProfile(false)
      showToast({
        variant: 'success',
        title: 'Trial profile updated',
        message: 'Title, condition, and phase changes were saved.',
      })
    } catch {
      setError('Trial details could not be updated. Your entered values are still here.')
      showToast({
        variant: 'error',
        title: 'Trial profile not saved',
        message: 'Review the highlighted trial details and try again.',
        announce: false,
      })
    } finally {
      setSaving(false)
    }
  }

  const startEditingCriteria = async () => {
    if (saving) return
    setSaving(true)
    setError('')
    try {
      await apiRequest<TrialVersion>(
        `/trials/${trialId}/versions/draft`,
        { method: 'POST' },
        token,
      )
      await load()
      showToast({
        variant: 'success',
        title: 'Criteria ready to edit',
        message: 'Add, change, or remove inclusion and exclusion criteria, then save the protocol.',
      })
    } catch (exception) {
      const message =
        exception instanceof ApiError && exception.code === 'TRIAL_DRAFT_EXISTS'
          ? 'Criteria are already open for editing.'
          : 'Criteria could not be opened for editing.'
      setError(message)
      showToast({ variant: 'error', title: 'Editing not started', message, announce: false })
    } finally {
      setSaving(false)
    }
  }

  const openAddCriterion = (kind: Criterion['kind']) => {
    setEditingCriterion(null)
    setCriterionKind(kind)
    setCriterionError('')
    setCriterionEditorOpen(true)
  }

  const openEditCriterion = (criterion: Criterion) => {
    setEditingCriterion(criterion)
    setCriterionKind(criterion.kind)
    setCriterionError('')
    setCriterionEditorOpen(true)
  }

  const closeCriterionEditor = () => {
    if (saving) return
    setCriterionEditorOpen(false)
    setEditingCriterion(null)
    setCriterionError('')
  }

  const saveCriterion = async (submission: GuidedCriterionSubmission) => {
    if (!activeDraft || saving) return
    setSaving(true)
    setCriterionError('')
    try {
      await apiRequest(
        editingCriterion
          ? `/trials/${trialId}/versions/${activeDraft.id}/guided-criteria/${editingCriterion.id}`
          : `/trials/${trialId}/versions/${activeDraft.id}/guided-criteria`,
        {
          method: editingCriterion ? 'PUT' : 'POST',
          body: JSON.stringify(submission),
        },
        token,
      )
      const wasEditing = Boolean(editingCriterion)
      setCriterionEditorOpen(false)
      setEditingCriterion(null)
      await load()
      showToast({
        variant: 'success',
        title: wasEditing ? 'Criterion updated' : 'Criterion added',
        message: wasEditing
          ? 'The structured screening rule was updated.'
          : `The ${submission.kind} criterion was added to the protocol.`,
      })
    } catch (exception) {
      const message =
        exception instanceof ApiError && exception.code === 'TRIAL_CRITERION_VALUE_INVALID'
          ? exception.message
          : 'The criterion could not be saved. Your selected values are still here.'
      setCriterionError(message)
      showToast({
        variant: 'error',
        title: 'Criterion not saved',
        message,
        announce: false,
      })
    } finally {
      setSaving(false)
    }
  }

  const saveUnsupportedCriterion = async (
    submission: UnsupportedCriterionSubmission,
  ) => {
    if (!activeDraft || saving) return
    setSaving(true)
    setCriterionError('')
    try {
      await apiRequest(
        `/trials/${trialId}/versions/${activeDraft.id}/unsupported-criteria`,
        {
          method: 'POST',
          body: JSON.stringify(submission),
        },
        token,
      )
      setCriterionEditorOpen(false)
      await load()
      showToast({
        variant: 'warning',
        title: 'Criterion saved for review',
        message: 'Map or remove this criterion before saving the protocol.',
      })
    } catch {
      const message = 'The unsupported criterion could not be saved. Its wording is still here.'
      setCriterionError(message)
      showToast({
        variant: 'error',
        title: 'Review criterion not saved',
        message,
        announce: false,
      })
    } finally {
      setSaving(false)
    }
  }

  const approveVersion = async () => {
    if (!activeDraft || saving) return
    setSaving(true)
    setError('')
    try {
      await apiRequest(
        `/trials/${trialId}/versions/${activeDraft.id}`,
        {
          method: 'PUT',
          body: JSON.stringify({
            version: activeDraft.version,
            status: 'approved',
            source_text: activeDraft.source_text,
          }),
        },
        token,
      )
      await load()
      showToast({
        variant: 'success',
        title: 'Protocol saved',
        message: 'The current criteria are ready for screening. Earlier screenings remain unchanged.',
      })
    } catch (exception) {
      const message =
        exception instanceof ApiError &&
        exception.code === 'TRIAL_VERSION_REVIEW_INCOMPLETE'
          ? 'Resolve every review-only criterion and add at least one structured criterion.'
          : exception instanceof ApiError && exception.code === 'TRIAL_RULE_INVALID'
            ? exception.message
          : 'The protocol could not be saved.'
      setError(message)
      showToast({
        variant: 'error',
        title: 'Protocol not saved',
        message,
        announce: false,
      })
    } finally {
      setSaving(false)
    }
  }

  const deleteCriterion = async (criterion: Criterion) => {
    if (!activeDraft || saving) return
    setSaving(true)
    try {
      await apiRequest(
        `/trials/${trialId}/versions/${activeDraft.id}/criteria/${criterion.id}`,
        { method: 'DELETE' },
        token,
      )
      await load()
      showToast({
        variant: 'success',
        title: 'Criterion removed',
        message: `${criterion.source_text} was removed from the protocol.`,
      })
    } catch {
      const message = 'The criterion could not be removed. No changes were made.'
      setError(message)
      showToast({ variant: 'error', title: 'Criterion not removed', message, announce: false })
    } finally {
      setSaving(false)
    }
  }

  const deleteTrial = async () => {
    if (deleting) return
    setDeleting(true)
    try {
      await apiRequest(`/trials/${trialId}`, { method: 'DELETE' }, token)
      navigate('/trials', { replace: true })
    } catch (exception) {
      setDeleteOpen(false)
      setError(
        exception instanceof ApiError && exception.code === 'TRIAL_HAS_SCREENING_HISTORY'
          ? 'This trial cannot be deleted because it is used by saved screening history.'
          : 'Trial could not be deleted. No changes were made.',
      )
    } finally {
      setDeleting(false)
    }
  }

  if (error && !trial) return <div className="form-error" role="alert">{error}</div>
  if (!trial) return <div className="loading-state">Loading trial…</div>

  const criteriaByKind: Record<Criterion['kind'], Criterion[]> = {
    inclusion: currentProtocol?.criteria.filter((criterion) => criterion.kind === 'inclusion') ?? [],
    exclusion: currentProtocol?.criteria.filter((criterion) => criterion.kind === 'exclusion') ?? [],
  }

  return (
    <section className="route-entry workspace-page">
      <Link className="back-link" to="/trials">← Trials</Link>
      <header className="page-heading">
        <h1>{trial.title}</h1>
        <button
          className="danger-button danger-button-subtle"
          type="button"
          onClick={() => setDeleteOpen(true)}
        >
          Delete trial
        </button>
      </header>

      <section className="demographics-panel trial-profile-panel" aria-labelledby="trial-profile-heading">
        <div className="demographics-heading">
          <h2 id="trial-profile-heading">Trial details</h2>
          {!editingProfile ? (
            <button className="secondary-button" type="button" onClick={beginProfileEdit}>
              Edit trial details
            </button>
          ) : null}
        </div>
        {editingProfile && profileDraft ? (
          <form className="demographics-form" onSubmit={saveTrial}>
            <div className="demographics-form-grid">
              <label>
                Trial title
                <input
                  autoFocus
                  required
                  value={profileDraft.title}
                  onChange={(event) =>
                    setProfileDraft({ ...profileDraft, title: event.target.value })}
                />
              </label>
              <label>
                Primary condition
                <input
                  required
                  value={profileDraft.condition}
                  onChange={(event) =>
                    setProfileDraft({ ...profileDraft, condition: event.target.value })}
                />
              </label>
              <label>
                Phase
                <input
                  value={profileDraft.phase}
                  onChange={(event) =>
                    setProfileDraft({ ...profileDraft, phase: event.target.value })}
                  placeholder="Optional"
                />
              </label>
            </div>
            <div className="demographics-actions">
              <button
                className="secondary-button"
                disabled={saving}
                type="button"
                onClick={() => {
                  setEditingProfile(false)
                  setProfileDraft(null)
                }}
              >
                Cancel
              </button>
              <button className="primary-button" disabled={saving} type="submit">
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </form>
        ) : (
          <dl className="demographics-summary">
            <div><dt>Primary condition</dt><dd>{trial.condition}</dd></div>
            <div><dt>Phase</dt><dd>{trial.phase ?? 'Not recorded'}</dd></div>
            <div><dt>Registry reference</dt><dd>{trial.registry_id}</dd></div>
          </dl>
        )}
      </section>

      {error ? <div className="form-error" role="alert">{error}</div> : null}
      {catalogError ? (
        <div className="form-error" role="alert">
          <span>{catalogError}</span>
          <button className="text-button" type="button" onClick={() => void loadCatalog()}>
            Try again
          </button>
        </div>
      ) : null}

      <TrialCriteriaSection
        currentProtocol={Boolean(currentProtocol)}
        criteriaByKind={criteriaByKind}
        editing={editingCriteria}
        saving={saving}
        catalogError={catalogError}
        canSave={Boolean(activeDraft?.criteria.length)}
        onAdd={openAddCriterion}
        onEdit={openEditCriterion}
        onRemove={(criterion) => { void deleteCriterion(criterion) }}
        onSave={() => { void approveVersion() }}
        onStartEditing={() => { void startEditingCriteria() }}
        catalog={catalog}
      />

      <TrialCriterionEditor
        open={criterionEditorOpen}
        presentation="inline"
        token={token}
        canCreateSupportedTerm={Boolean(user?.is_catalog_admin)}
        entries={catalog}
        criterion={editingCriterion}
        initialKind={criterionKind}
        saving={saving}
        error={criterionError}
        onCancel={closeCriterionEditor}
        onSubmit={(submission) => void saveCriterion(submission)}
        onSubmitUnsupported={(submission) => void saveUnsupportedCriterion(submission)}
        onCatalogEntryCreated={(entry) => setCatalog((current) => [...current, entry])}
      />

      <RelatedScreenings screenings={screenings} counterpart="patient" />
      <TechnicalDetails>
        <dl className="technical-details-list">
          <div><dt>Record reference</dt><dd>{trial.registry_id}</dd></div>
          <div>
            <dt>Protocol status</dt>
            <dd>{editingCriteria ? 'Draft changes in progress' : 'Current protocol saved'}</dd>
          </div>
          {currentProtocol ? (
            <div><dt>Protocol version</dt><dd>{currentProtocol.version}</dd></div>
          ) : null}
          {trial.updated_at ? (
            <div><dt>Last updated</dt><dd>{new Date(trial.updated_at).toLocaleString()}</dd></div>
          ) : null}
        </dl>
      </TechnicalDetails>

      <ConfirmationDialog
        open={deleteOpen}
        title="Delete this trial?"
        confirmLabel="Delete trial"
        busyLabel="Deleting…"
        busy={deleting}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void deleteTrial()}
      >
        <p>
          <strong>{trial.title}</strong> will be removed. Trials used by saved screenings
          cannot be deleted.
        </p>
      </ConfirmationDialog>
    </section>
  )
}
