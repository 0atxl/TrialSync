import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiRequest, type Trial } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function TrialDetailPage() {
  const { trialId = '' } = useParams()
  const { token } = useAuth()
  const [trial, setTrial] = useState<Trial | null>(null)
  const [error, setError] = useState('')
  const [versionNumber, setVersionNumber] = useState('1')
  const [kind, setKind] = useState('inclusion')
  const [order, setOrder] = useState('1')
  const [sourceText, setSourceText] = useState('')

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
    try {
      await apiRequest(`/trials/${trialId}/versions/${version.id}/criteria`, {
        method: 'POST',
        body: JSON.stringify({ kind, order: Number(order), source_text: sourceText, required: true }),
      }, token)
      setSourceText('')
      setOrder(String(Number(order) + 1))
      await load()
    } catch { setError('Criterion could not be saved. Each order number must be unique.') }
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

  if (error && !trial) return <div className="form-error" role="alert">{error}</div>
  if (!trial) return <div className="loading-state">Loading trial…</div>
  const activeVersion = trial.versions.at(-1)

  return (
    <section className="route-entry workspace-page">
      <Link className="back-link" to="/trials">← Trials</Link>
      <header className="page-heading"><p className="eyebrow">{trial.registry_id}</p><h1>{trial.title}</h1></header>
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
          <div>{trial.versions.map((version) => <div className="version-row" key={version.id}><strong>Version {version.version}</strong><span>{version.status}</span></div>)}</div>
        </section>
        <section>
          <h2>Ordered criteria</h2>
          <form className="criterion-form" onSubmit={addCriterion}>
            <div className="form-pair"><label>Kind<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="inclusion">Inclusion</option><option value="exclusion">Exclusion</option></select></label><label>Order<input min="1" required type="number" value={order} onChange={(event) => setOrder(event.target.value)} /></label></div>
            <label>Protocol criterion<textarea required rows={3} value={sourceText} onChange={(event) => setSourceText(event.target.value)} /></label>
            <button className="primary-button" disabled={!activeVersion} type="submit">Add criterion</button>
          </form>
          {error && <div className="form-error" role="alert">{error}</div>}
          <div className="record-list">
            {activeVersion?.criteria.length ? activeVersion.criteria.map((criterion) => (
              <article className="criterion-row" key={criterion.id}><span className="criterion-order">{criterion.order}</span><div className="criterion-copy"><span className="record-kind">{criterion.kind}</span><strong>{criterion.source_text}</strong></div><button className="text-button danger" onClick={() => void deleteCriterion(activeVersion.id, criterion.id)} type="button">Remove</button></article>
            )) : <div className="empty-state"><h2>No criteria</h2><p>Create a draft version, then add ordered rules.</p></div>}
          </div>
        </section>
      </div>
    </section>
  )
}
