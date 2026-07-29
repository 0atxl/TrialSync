import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  ApiError,
  apiRequest,
  type Criterion,
  type PatientFactCatalog,
  type PatientFactCatalogEntry,
  type Trial,
  type TrialVersion,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ConfirmationDialog } from '../components/ConfirmationDialog'
import { useToast } from '../components/ToastProvider'
import {
  criterionSubjectKey,
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
  const { token } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [trial, setTrial] = useState<Trial | null>(null)
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
      setTrial(await apiRequest<Trial>(`/trials/${trialId}`, {}, token))
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
  const approvedVersions = useMemo(
    () => trial?.versions.filter((version) => version.status === 'approved') ?? [],
    [trial?.versions],
  )

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

  const createDraft = async () => {
    if (saving) return
    setSaving(true)
    setError('')
    try {
      const draft = await apiRequest<TrialVersion>(
        `/trials/${trialId}/versions/draft`,
        { method: 'POST' },
        token,
      )
      await load()
      showToast({
        variant: 'success',
        title: approvedVersions.length ? 'Draft revision created' : 'Criteria draft created',
        message: approvedVersions.length
          ? `Revision ${draft.version} copied the latest approved criteria for safe editing.`
          : 'Add inclusion and exclusion criteria using the guided catalog.',
      })
    } catch (exception) {
      const message =
        exception instanceof ApiError && exception.code === 'TRIAL_DRAFT_EXISTS'
          ? 'This trial already has an editable draft.'
          : 'A criteria draft could not be created.'
      setError(message)
      showToast({ variant: 'error', title: 'Draft not created', message, announce: false })
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
          : `The ${submission.kind} criterion was added to the current draft.`,
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
        message: 'The draft cannot be approved until this criterion is mapped or removed.',
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
        title: 'Protocol approved',
        message: `Revision ${activeDraft.version} is locked and available for screening.`,
      })
    } catch (exception) {
      const message =
        exception instanceof ApiError &&
        exception.code === 'TRIAL_VERSION_REVIEW_INCOMPLETE'
          ? 'Resolve every review-only criterion and add at least one structured criterion.'
          : 'The protocol could not be approved.'
      setError(message)
      showToast({
        variant: 'error',
        title: 'Protocol not approved',
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
        message: `${criterion.source_text} was removed from the current draft.`,
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
    inclusion: activeDraft?.criteria.filter((criterion) => criterion.kind === 'inclusion') ?? [],
    exclusion: activeDraft?.criteria.filter((criterion) => criterion.kind === 'exclusion') ?? [],
  }

  return (
    <section className="route-entry workspace-page">
      <Link className="back-link" to="/trials">← Trials</Link>
      <header className="page-heading">
        <div>
          <p className="eyebrow">{trial.registry_id}</p>
          <h1>{trial.title}</h1>
        </div>
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
          <div>
            <p className="eyebrow">Protocol profile</p>
            <h2 id="trial-profile-heading">Trial details</h2>
          </div>
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
            <div><dt>Title</dt><dd>{trial.title}</dd></div>
            <div><dt>Primary condition</dt><dd>{trial.condition}</dd></div>
            <div><dt>Phase</dt><dd>{trial.phase ?? 'Not recorded'}</dd></div>
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

      <section className="trial-criteria-workspace" aria-labelledby="trial-criteria-heading">
        <div className="clinical-details-heading">
          <div>
            <p className="eyebrow">Deterministic screening</p>
            <h2 id="trial-criteria-heading">Eligibility criteria</h2>
            <p>
              Build readable inclusion and exclusion rules from the same controlled
              clinical catalog used by patient records.
            </p>
          </div>
          {activeDraft ? (
            <button
              className="primary-button"
              disabled={saving || activeDraft.criteria.length === 0}
              type="button"
              onClick={() => void approveVersion()}
            >
              {saving ? 'Saving…' : 'Approve protocol'}
            </button>
          ) : (
            <button
              className="primary-button"
              disabled={saving}
              type="button"
              onClick={() => void createDraft()}
            >
              {saving
                ? 'Creating…'
                : approvedVersions.length
                  ? 'Create draft revision'
                  : 'Start criteria draft'}
            </button>
          )}
        </div>

        {activeDraft ? (
          <>
            <div className="draft-banner" role="status">
              <div>
                <strong>Current draft</strong>
                <span>
                  Changes affect only this draft. Approved revisions and saved screenings
                  remain unchanged.
                </span>
              </div>
              <small>Revision {activeDraft.version}</small>
            </div>
            <div className="trial-criteria-groups">
              {(['inclusion', 'exclusion'] as const).map((kind) => (
                <section className={`trial-criterion-group criterion-${kind}`} key={kind}>
                  <header>
                    <div>
                      <p className="eyebrow">
                        {kind === 'inclusion' ? 'Must be satisfied' : 'Must not be present'}
                      </p>
                      <h3>{kind === 'inclusion' ? 'Inclusion criteria' : 'Exclusion criteria'}</h3>
                    </div>
                    <button
                      className="secondary-button"
                      disabled={Boolean(catalogError)}
                      type="button"
                      onClick={() => openAddCriterion(kind)}
                    >
                      Add criterion
                    </button>
                  </header>
                  {criteriaByKind[kind].length === 0 ? (
                    <div className="trial-criterion-empty">
                      No {kind} criteria in this draft.
                    </div>
                  ) : (
                    <div className="trial-criterion-rows">
                      {criteriaByKind[kind].map((criterion) => {
                        const supported = Boolean(
                          criterion.normalized_rule &&
                          criterionSubjectKey(criterion, catalog),
                        )
                        return (
                          <article className="trial-criterion-row" key={criterion.id}>
                            <div>
                              <strong>{criterion.source_text}</strong>
                              <span>
                                {supported
                                  ? 'Structured screening rule'
                                  : 'Review only · no screening rule'}
                              </span>
                            </div>
                            <div className="record-actions">
                              {supported ? (
                                <button
                                  className="text-button"
                                  type="button"
                                  onClick={() => openEditCriterion(criterion)}
                                >
                                  Edit
                                </button>
                              ) : (
                                <span className="unsupported-detail">Needs mapping</span>
                              )}
                              <button
                                className="text-button danger"
                                disabled={saving}
                                type="button"
                                onClick={() => void deleteCriterion(criterion)}
                              >
                                Remove
                              </button>
                            </div>
                          </article>
                        )
                      })}
                    </div>
                  )}
                </section>
              ))}
            </div>
          </>
        ) : (
          <div className="trial-draft-empty">
            <strong>
              {approvedVersions.length
                ? 'The approved protocol is protected.'
                : 'No criteria draft yet.'}
            </strong>
            <p>
              {approvedVersions.length
                ? 'Create a draft revision to copy and safely edit the latest approved criteria.'
                : 'Start a draft, then add criteria without entering codes, units, order numbers, or version numbers.'}
            </p>
          </div>
        )}

        <section className="protocol-history" aria-labelledby="protocol-history-heading">
          <div>
            <p className="eyebrow">Reproducibility</p>
            <h3 id="protocol-history-heading">Protocol history</h3>
          </div>
          <div>
            {trial.versions.length ? trial.versions.map((version) => (
              <span className={`protocol-history-item ${version.status}`} key={version.id}>
                <strong>
                  {version.status === 'draft' ? 'Current draft' : 'Approved'}
                </strong>
                <small>Revision {version.version} · {version.criteria.length} criteria</small>
              </span>
            )) : <span className="protocol-history-empty">No revisions created.</span>}
          </div>
        </section>
      </section>

      <TrialCriterionEditor
        open={criterionEditorOpen}
        entries={catalog}
        criterion={editingCriterion}
        initialKind={criterionKind}
        saving={saving}
        error={criterionError}
        onCancel={closeCriterionEditor}
        onSubmit={(submission) => void saveCriterion(submission)}
        onSubmitUnsupported={(submission) => void saveUnsupportedCriterion(submission)}
      />
      <ConfirmationDialog
        open={deleteOpen}
        eyebrow="Permanent action"
        title="Delete this trial?"
        confirmLabel="Delete trial"
        busyLabel="Deleting…"
        busy={deleting}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void deleteTrial()}
      >
        <p>
          <strong>{trial.title}</strong> and its draft protocol data will be removed.
          Approved protocols referenced by saved screening history remain protected.
        </p>
      </ConfirmationDialog>
    </section>
  )
}
