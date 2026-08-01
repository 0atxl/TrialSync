import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { apiRequest, type Trial } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function TrialsPage() {
  const { token } = useAuth()
  const [trials, setTrials] = useState<Trial[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    setLoading(true)
    try { setTrials(await apiRequest('/trials', {}, token)); setError('') }
    catch { setError('Trials could not be loaded.') }
    finally { setLoading(false) }
  }, [token])
  useEffect(() => { void load() }, [load])
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    return term ? trials.filter((trial) => `${trial.title} ${trial.registry_id} ${trial.condition}`.toLowerCase().includes(term)) : trials
  }, [trials, query])

  return <section className="route-entry workspace-page">
    <header className="page-heading"><div><p className="eyebrow">Protocol workspace</p><h1>Trials</h1><p>Current protocols with clear inclusion and exclusion criteria.</p></div><div className="page-actions"><Link className="secondary-button" to="/imports/new?kind=trial">Import text or PDF</Link><Link className="primary-button" to="/trials/new">Add trial</Link></div></header>
    <div className="list-toolbar"><label className="search-field"><span>Search trials</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Type a title, registry ID, or condition" /></label><span>{filtered.length} of {trials.length} protocols</span></div>
    {error ? <div className="form-error" role="alert">{error}</div> : loading ? <div className="loading-state">Loading trials…</div> : filtered.length === 0 ? <div className="empty-state"><h2>{trials.length ? 'No matching trials' : 'No trials yet'}</h2><p>{trials.length ? 'Try a different title, condition, or registry ID.' : 'Add a fictional protocol to begin.'}</p></div> : <div className="record-table"><div className="record-table-head" aria-hidden="true"><span>Protocol</span><span>Condition</span><span>Criteria</span><span /></div>{filtered.map((trial) => <article className="record-table-row" key={trial.id}><div><strong>{trial.title}</strong><small>{trial.registry_id}</small></div><span>{trial.condition}{trial.phase ? ` · ${trial.phase}` : ''}</span><span className="tabular">{trial.versions.find((version) => version.status === 'draft')?.criteria.length ?? trial.versions.filter((version) => version.status === 'approved').at(-1)?.criteria.length ?? 0}</span><Link to={`/trials/${trial.id}`}>Review protocol</Link></article>)}</div>}
  </section>
}
