import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { apiRequest, type Trial } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function TrialsPage() {
  const { token } = useAuth()
  const [trials, setTrials] = useState<Trial[]>([])
  const [registryId, setRegistryId] = useState('')
  const [title, setTitle] = useState('')
  const [condition, setCondition] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    setLoading(true)
    try { setTrials(await apiRequest<Trial[]>('/trials', {}, token)); setError('') }
    catch { setError('Trials could not be loaded.') }
    finally { setLoading(false) }
  }, [token])
  useEffect(() => { void load() }, [load])
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await apiRequest('/trials', { method: 'POST', body: JSON.stringify({ registry_id: registryId, title, condition }) }, token)
      setRegistryId(''); setTitle(''); setCondition(''); await load()
    } catch { setError('The trial could not be saved.') }
  }
  return <section className="route-entry workspace-page"><header className="page-heading"><div><p className="eyebrow">Protocol workspace</p><h1>Trials</h1><p>Create synthetic protocols and ordered inclusion or exclusion criteria.</p></div></header><form className="inline-form trial-form" onSubmit={submit}><label>Registry ID<input required value={registryId} onChange={(event) => setRegistryId(event.target.value)} placeholder="SYN-NCT-001" /></label><label>Title<input required value={title} onChange={(event) => setTitle(event.target.value)} /></label><label>Condition<input required value={condition} onChange={(event) => setCondition(event.target.value)} /></label><button className="primary-button" type="submit">Add trial</button></form>{error && <div className="form-error" role="alert">{error}</div>}{loading ? <div className="loading-state">Loading trials…</div> : trials.length === 0 ? <div className="empty-state"><h2>No trials yet</h2><p>Add a fictional protocol above.</p></div> : <div className="data-table" role="table"><div className="data-row data-header"><span>Registry ID</span><span>Title</span><span>Versions</span><span /></div>{trials.map((trial) => <div className="data-row" key={trial.id}><strong>{trial.registry_id}</strong><span>{trial.title}</span><span>{trial.versions.length}</span><Link to={`/trials/${trial.id}`}>Review</Link></div>)}</div>}</section>
}
