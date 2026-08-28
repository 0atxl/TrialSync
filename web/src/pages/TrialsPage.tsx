import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { apiRequest, type Trial } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Pagination } from '../components/Pagination'

const PAGE_SIZE = 10

export function TrialsPage() {
  const { token } = useAuth()
  const [trials, setTrials] = useState<Trial[]>([])
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setTrials(await apiRequest('/trials', {}, token))
      setError('')
    } catch {
      setError('Trials could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    return term
      ? trials.filter((trial) => `${trial.title} ${trial.condition}`.toLowerCase().includes(term))
      : trials
  }, [trials, query])

  useEffect(() => {
    setPage(1)
  }, [query])

  const paginated = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return filtered.slice(start, start + PAGE_SIZE)
  }, [filtered, page])

  return (
    <section className="route-entry workspace-page">
      <header className="page-heading">
        <h1>Trials</h1>
        <div className="page-actions">
          <Link className="primary-button" to="/trials/new">Add trial</Link>
        </div>
      </header>
      <div className="list-toolbar">
        <label className="search-field">
          <span>Search trials</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Trial title or condition"
          />
        </label>
        <span>{filtered.length} of {trials.length}</span>
      </div>
      {error ? (
        <div className="form-error" role="alert">{error}</div>
      ) : loading ? (
        <div className="loading-state">Loading trials…</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <h2>{trials.length ? 'No matching trials' : 'No trials yet'}</h2>
          <p>{trials.length ? 'Try another title or condition.' : 'Add a trial to begin.'}</p>
        </div>
      ) : (
        <>
          <div className="record-table">
            <div className="record-table-head" aria-hidden="true">
              <span>Trial</span><span>Condition</span><span>Criteria</span><span />
            </div>
            {paginated.map((trial) => {
              const draft = trial.versions.find((version) => version.status === 'draft')
              const approved = trial.versions
                .filter((version) => version.status === 'approved')
                .at(-1)
              return (
                <article className="record-table-row" key={trial.id}>
                  <div><strong>{trial.title}</strong></div>
                  <span>{trial.condition}{trial.phase ? ` · ${trial.phase}` : ''}</span>
                  <span className="tabular">{draft?.criteria.length ?? approved?.criteria.length ?? 0}</span>
                  <Link to={`/trials/${trial.id}`}>Open</Link>
                </article>
              )
            })}
          </div>
          <Pagination currentPage={page} totalItems={filtered.length} pageSize={PAGE_SIZE} onPageChange={setPage} />
        </>
      )}
    </section>
  )
}
