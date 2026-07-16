import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { apiRequest, type Screening, type ScreeningState } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { screeningTrialLabel, stateLabel } from './screeningHelpers'

export function ScreeningHistoryPage() {
  const { token, logout } = useAuth()
  const [items, setItems] = useState<Screening[]>([])
  const [state, setState] = useState<'all' | ScreeningState>('all')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setItems(await apiRequest('/screenings', {}, token)); setError('') }
    catch (exception) {
      setError(exception instanceof Error && 'status' in exception && (exception as { status: number }).status === 401 ? 'Your session has expired. Sign in again.' : 'Screening history could not be loaded.')
    } finally { setLoading(false) }
  }, [token])
  useEffect(() => { void load() }, [load])

  const filtered = useMemo(() => items.filter((item) =>
    (state === 'all' || item.overall_state === state)
    && `${item.patient_snapshot?.display_name} ${item.patient_snapshot?.external_id} ${screeningTrialLabel(item)}`.toLowerCase().includes(query.toLowerCase()),
  ), [items, state, query])

  return <section className="route-entry workspace-page">
    <header className="page-heading"><div><p className="eyebrow">Reproducible history</p><h1>Screenings</h1><p>Immutable comparisons with criterion-level evidence and approved protocol versions.</p></div><div className="page-actions"><Link className="secondary-button" to="/batches/new">Batch screening</Link><Link className="primary-button" to="/screenings/new">New screening</Link></div></header>
    <div className="history-toolbar"><label className="search-field"><span>Search history</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Patient or trial" /></label><label>Overall state<select value={state} onChange={(event) => setState(event.target.value as typeof state)}><option value="all">All results</option><option value="potentially_eligible">Potentially eligible</option><option value="likely_ineligible">Likely ineligible</option><option value="needs_review">Needs review</option></select></label></div>
    {error ? <div className="form-error" role="alert">{error} {error.includes('expired') && <button className="text-button" onClick={logout}>Sign in</button>}</div> : loading ? <div className="loading-state">Loading saved screenings…</div> : filtered.length === 0 ? <div className="empty-state"><h2>No matching screenings</h2><p>Adjust the filters or run a new screening.</p></div> : <section className="history-table" aria-label="Screening history"><div className="history-table-head" aria-hidden="true"><span>Patient and trial</span><span>Result</span><span>Criteria</span><span>Date</span><span /></div>{filtered.map((item) => <article className="history-compact-row" key={item.id}><div><strong>{item.patient_snapshot?.display_name ?? 'Patient'}</strong><small>{item.patient_snapshot?.external_id} · {screeningTrialLabel(item)}</small></div><span className={`state state-${item.overall_state}`}>{stateLabel(item.overall_state)}</span><span className="criterion-counts">{item.counts.pass_count} pass · {item.counts.fail_count} fail · {item.counts.unknown_count} unknown</span><time>{item.screening_date}</time><Link className="row-action" to={`/screenings/${item.id}`}>Review</Link></article>)}</section>}
  </section>
}
