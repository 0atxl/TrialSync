import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError, apiRequest, type Trial } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ConfirmationDialog } from '../components/ConfirmationDialog'

type RuleTemplate = 'age_between' | 'condition_present' | 'observation_between'

export function TrialDetailPage() {
  const { trialId = '' } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()
  const [trial, setTrial] = useState<Trial | null>(null)
  const [error, setError] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [versionNumber, setVersionNumber] = useState('1')
  const [kind, setKind] = useState('inclusion')
  const [order, setOrder] = useState('1')
  const [sourceText, setSourceText] = useState('')
  const [ruleTemplate, setRuleTemplate] = useState<RuleTemplate>('age_between')
  const [ruleConcept, setRuleConcept] = useState('')
  const [ruleMinimum, setRuleMinimum] = useState('18')
  const [ruleMaximum, setRuleMaximum] = useState('75')
  const [ruleUnit, setRuleUnit] = useState('year')

  const load = useCallback(async () => {
    try {
      setTrial(await apiRequest<Trial>(`/trials/${trialId}`, {}, token))
      setError('')
    } catch {
      setError('Trial could not be loaded.')
    }
  }, [token, trialId])

  useEffect(() => { void load() }, [load])

  const saveTrial = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    try {
      await apiRequest(`/trials/${trialId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title: values.get('title'), condition: values.get('condition'), phase: values.get('phase') || null,
        }),
      }, token)
      await load()
    } catch { setError('Trial details could not be updated.') }
  }

  const addVersion = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await apiRequest(`/trials/${trialId}/versions`, {
        method: 'POST', body: JSON.stringify({ version: Number(versionNumber), status: 'draft' }),
      }, token)
      await load()
    } catch { setError('Trial version could not be saved.') }
  }

  const addCriterion = async (event: FormEvent) => {
    event.preventDefault()
    const version = trial?.versions.at(-1)
    if (!version) { setError('Create a draft version first.'); return }
    const minimum = Number(ruleMinimum)
    const maximum = Number(ruleMaximum)
    const usesRange = ruleTemplate !== 'condition_present'
    if (usesRange && (!Number.isFinite(minimum) || !Number.isFinite(maximum) || minimum > maximum)) {
      setError('Enter a valid deterministic range with the minimum at or below the maximum.')
      return
    }
    const normalizedRule = ruleTemplate === 'age_between'
      ? { op: 'between', fact: 'demographic.age', min: minimum, max: maximum, unit: 'year' }
      : ruleTemplate === 'condition_present'
        ? { op: 'present', fact: `condition.${ruleConcept.trim()}` }
        : { op: 'between', fact: `observation.${ruleConcept.trim()}`, min: minimum, max: maximum, unit: ruleUnit.trim(), selection: 'latest' }
    if ((ruleTemplate !== 'age_between' && !ruleConcept.trim()) || (ruleTemplate === 'observation_between' && !ruleUnit.trim())) {
      setError('Complete every deterministic rule field before adding the criterion.')
      return
    }
    try {
      await apiRequest(`/trials/${trialId}/versions/${version.id}/criteria`, {
        method: 'POST',
        body: JSON.stringify({ kind, order: Number(order), source_text: sourceText, normalized_rule: normalizedRule, required: true }),
      }, token)
      setSourceText('')
      setOrder(String(Number(order) + 1))
      await load()
    } catch { setError('Criterion could not be saved. Each order number must be unique.') }
  }

  const approveVersion = async (versionId: string, versionNumber: number, sourceText: string | null) => {
    try {
      await apiRequest(`/trials/${trialId}/versions/${versionId}`, {
        method: 'PUT',
        body: JSON.stringify({ version: versionNumber, status: 'approved', source_text: sourceText }),
      }, token)
      await load()
    } catch {
      setError('The trial version could not be approved. Review its criteria and rules first.')
    }
  }

  const deleteCriterion = async (versionId: string, criterionId: string) => {
    try {
      await apiRequest(
        `/trials/${trialId}/versions/${versionId}/criteria/${criterionId}`,
        { method: 'DELETE' }, token,
      )
      await load()
    } catch { setError('Criterion could not be removed.') }
  }

  const deleteTrial = async () => {
    setDeleting(true)
    try {
      await apiRequest(`/trials/${trialId}`, { method: 'DELETE' }, token)
      navigate('/trials', { replace: true })
    } catch (exception) {
      setDeleteOpen(false)
      setError(exception instanceof ApiError && exception.code === 'TRIAL_HAS_SCREENING_HISTORY'
        ? 'This trial cannot be deleted because it is used by saved screening history.'
        : 'Trial could not be deleted. No changes were made.')
    } finally {
      setDeleting(false)
    }
  }

  if (error && !trial) return <div className="form-error" role="alert">{error}</div>
  if (!trial) return <div className="loading-state">Loading trial…</div>
  const activeVersion = trial.versions.at(-1)

  return (
    <section className="route-entry workspace-page">
      <Link className="back-link" to="/trials">← Trials</Link>
      <header className="page-heading"><div><p className="eyebrow">{trial.registry_id}</p><h1>{trial.title}</h1></div><button className="danger-button danger-button-subtle" type="button" onClick={() => setDeleteOpen(true)}>Delete trial</button></header>
      <form className="profile-form" onSubmit={saveTrial}>
        <label>Title<input name="title" required defaultValue={trial.title} /></label>
        <label>Condition<input name="condition" required defaultValue={trial.condition} /></label>
        <label>Phase<input name="phase" defaultValue={trial.phase ?? ''} /></label>
        <button className="secondary-button" type="submit">Save trial</button>
      </form>
      <div className="split-workspace">
        <section>
          <h2>Protocol versions</h2>
          <form className="compact-form" onSubmit={addVersion}><label>Version<input min="1" required type="number" value={versionNumber} onChange={(event) => setVersionNumber(event.target.value)} /></label><button className="secondary-button" type="submit">Create draft</button></form>
          <div>{trial.versions.map((version) => <div className="version-row" key={version.id}><strong>Version {version.version}</strong><span>{version.status}</span>{version.status === 'draft' && <button className="text-button" type="button" onClick={() => void approveVersion(version.id, version.version, version.source_text)}>Approve version</button>}</div>)}</div>
        </section>
        <section>
          <h2>Ordered criteria</h2>
          <form className="criterion-form" onSubmit={addCriterion}>
            <div className="form-pair"><label>Kind<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="inclusion">Inclusion</option><option value="exclusion">Exclusion</option></select></label><label>Order<input min="1" required type="number" value={order} onChange={(event) => setOrder(event.target.value)} /></label></div>
            <label>Protocol criterion<textarea required rows={3} value={sourceText} onChange={(event) => setSourceText(event.target.value)} /></label>
            <fieldset className="rule-builder"><legend>Deterministic rule</legend><label>Rule template<select value={ruleTemplate} onChange={(event) => setRuleTemplate(event.target.value as RuleTemplate)}><option value="age_between">Age between</option><option value="condition_present">Condition present</option><option value="observation_between">Observation between</option></select></label>{ruleTemplate !== 'age_between' && <label>Normalized concept<input required value={ruleConcept} onChange={(event) => setRuleConcept(event.target.value)} placeholder={ruleTemplate === 'condition_present' ? 'type2_diabetes' : 'hba1c'} /></label>}{ruleTemplate !== 'condition_present' && <div className="form-pair"><label>Minimum<input required inputMode="decimal" value={ruleMinimum} onChange={(event) => setRuleMinimum(event.target.value)} /></label><label>Maximum<input required inputMode="decimal" value={ruleMaximum} onChange={(event) => setRuleMaximum(event.target.value)} /></label></div>}{ruleTemplate === 'observation_between' && <label>Unit<input required value={ruleUnit} onChange={(event) => setRuleUnit(event.target.value)} placeholder="%" /></label>}<small>The saved rule—not the wording alone—drives deterministic screening.</small></fieldset>
            <button className="primary-button" disabled={!activeVersion} type="submit">Add criterion</button>
          </form>
          {error && <div className="form-error" role="alert">{error}</div>}
          <div className="record-list">
            {activeVersion?.criteria.length ? activeVersion.criteria.map((criterion) => (
              <article className="criterion-row" key={criterion.id}><span className="criterion-order">{criterion.order}</span><div className="criterion-copy"><span className="record-kind">{criterion.kind}</span><strong>{criterion.source_text}</strong><small>{criterion.normalized_rule ? 'Deterministic rule reviewed' : 'Rule review required'}</small></div><button className="text-button danger" onClick={() => void deleteCriterion(activeVersion.id, criterion.id)} type="button">Remove</button></article>
            )) : <div className="empty-state"><h2>No criteria</h2><p>Create a draft version, then add ordered rules.</p></div>}
          </div>
        </section>
      </div>
      <ConfirmationDialog open={deleteOpen} eyebrow="Permanent action" title="Delete this trial?" confirmLabel="Delete trial" busyLabel="Deleting…" busy={deleting} onCancel={() => setDeleteOpen(false)} onConfirm={() => void deleteTrial()}>
        <p><strong>{trial.title}</strong> and its protocol versions will be removed. Trials referenced by saved screening history are protected and cannot be deleted.</p>
      </ConfirmationDialog>
    </section>
  )
}
