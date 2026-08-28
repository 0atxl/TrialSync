import { Search } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  apiRequest,
  type DropoutWorkflowStatus,
  type DropoutWorklistRow,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Pagination } from '../components/Pagination'
import { ResearchNav } from '../components/ResearchNav'

const statusOrder: DropoutWorkflowStatus[] = [
  'not_started',
  'information_needed',
  'ready',
  'predicted',
]

const statusLabels: Record<DropoutWorkflowStatus, string> = {
  not_started: 'Not started',
  information_needed: 'Information needed',
  ready: 'Ready to predict',
  predicted: 'Estimate available',
}

const actionLabels: Record<DropoutWorklistRow['next_action'], string> = {
  start_follow_up: 'Start follow-up',
  review_day30: 'Review information',
  predict: 'Predict dropout risk',
  view_prediction: 'View estimate',
}

const bandLabels = {
  lower: 'Lower',
  near_threshold: 'Near threshold',
  higher: 'Higher',
}

const PAGE_SIZE = 15

function estimateLabel(row: DropoutWorklistRow) {
  return row.estimate ? `${(row.estimate.probability * 100).toFixed(1)}%` : '—'
}

export function RecruitmentOverviewPage() {
  const { token } = useAuth()
  const [rows, setRows] = useState<DropoutWorklistRow[]>([])
  const [status, setStatus] = useState<DropoutWorkflowStatus | 'all'>('all')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await apiRequest<DropoutWorklistRow[]>('/research/risk/worklist', {}, token))
      setError('')
    } catch {
      setError('Dropout follow-up could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const counts = useMemo(() => Object.fromEntries(statusOrder.map((value) => [
    value,
    rows.filter((row) => row.workflow_status === value).length,
  ])) as Record<DropoutWorkflowStatus, number>, [rows])

  const bands = useMemo(() => ({
    lower: rows.filter((row) => row.estimate?.research_label === 'lower').length,
    near_threshold: rows.filter((row) => row.estimate?.research_label === 'near_threshold').length,
    higher: rows.filter((row) => row.estimate?.research_label === 'higher').length,
  }), [rows])

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    return rows.filter((row) =>
      (status === 'all' || row.workflow_status === status)
      && (!term || `${row.patient_name} ${row.trial_title}`.toLowerCase().includes(term)))
  }, [query, rows, status])

  useEffect(() => {
    setPage(1)
  }, [query, status])

  const paginated = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return visible.slice(start, start + PAGE_SIZE)
  }, [visible, page])

  return (
    <section className="route-entry workspace-page research-page dropout-page">
      <ResearchNav />
      <header className="page-heading research-page-heading"><h1>Dropout follow-up</h1></header>
      <p className="research-boundary overview-boundary">Dropout estimates are separate from eligibility.</p>

      {error ? (
        <div className="form-error" role="alert">{error}<button className="text-button" type="button" onClick={() => { void load() }}>Retry</button></div>
      ) : loading ? (
        <div className="loading-state">Loading follow-up status…</div>
      ) : rows.length === 0 ? (
        <div className="empty-state"><h2>No eligible screenings</h2><p>Potentially eligible saved screenings will appear here.</p></div>
      ) : (
        <>
          <div className="dropout-summary-grid">
            <section className="dropout-workflow-summary" aria-labelledby="workflow-summary-title">
              <div className="section-heading"><h2 id="workflow-summary-title">Follow-up status</h2><strong>{rows.length}</strong></div>
              <div className="dropout-status-bar" aria-hidden="true">
                {statusOrder.map((value) => <i className={`dropout-${value}`} key={value} style={{ width: `${counts[value] / rows.length * 100}%` }} />)}
              </div>
              <div className="dropout-status-filters">
                {statusOrder.map((value) => (
                  <button aria-pressed={status === value} className={status === value ? 'active' : ''} key={value} type="button" onClick={() => setStatus((current) => current === value ? 'all' : value)}>
                    <span>{statusLabels[value]}</span><strong>{counts[value]}</strong>
                  </button>
                ))}
              </div>
            </section>

            <section className="dropout-estimate-summary" aria-labelledby="estimate-summary-title">
              <div className="section-heading"><h2 id="estimate-summary-title">Available estimates</h2><strong>{counts.predicted}</strong></div>
              <div className="dropout-band-chart">
                {(Object.keys(bands) as Array<keyof typeof bands>).map((band) => {
                  const denominator = Math.max(1, counts.predicted)
                  return <div key={band}><span>{bandLabels[band]}</span><div><i className={`band-${band}`} style={{ width: `${bands[band] / denominator * 100}%` }} /></div><strong>{bands[band]}</strong></div>
                })}
              </div>
            </section>
          </div>

          <div className="dropout-toolbar">
            <label className="search-field"><Search aria-hidden="true" size={17} /><span className="sr-only">Search follow-up records</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search patient or trial" /></label>
            <span>{visible.length} of {rows.length}</span>
          </div>

          {visible.length ? (
            <>
              <div className="dropout-worklist" role="table" aria-label="Dropout follow-up worklist">
                <div className="dropout-worklist-head" role="row"><span>Patient</span><span>Trial</span><span>Follow-up</span><span>Estimate</span><span>Updated</span><span /></div>
                {paginated.map((row) => (
                  <div className="dropout-worklist-row" role="row" key={row.screening_id}>
                    <strong role="cell">{row.patient_name}</strong>
                    <span role="cell">{row.trial_title}</span>
                    <span role="cell" className={`dropout-state dropout-state-${row.workflow_status}`}>{statusLabels[row.workflow_status]}</span>
                    <span role="cell" className="dropout-estimate">{estimateLabel(row)}{row.estimate ? <small>by day {row.estimate.horizon_day}</small> : null}</span>
                    <time role="cell" dateTime={row.updated_at}>{new Date(row.updated_at).toLocaleDateString()}</time>
                    <span role="cell" className="dropout-row-action"><Link to={`/screenings/${row.screening_id}/dropout`}>{actionLabels[row.next_action]}</Link></span>
                  </div>
                ))}
              </div>
              <Pagination currentPage={page} totalItems={visible.length} pageSize={PAGE_SIZE} onPageChange={setPage} />
            </>
          ) : (
            <div className="empty-state compact-empty"><h2>No matching follow-up records</h2><button className="text-button" type="button" onClick={() => { setQuery(''); setStatus('all') }}>Clear filters</button></div>
          )}
        </>
      )}
    </section>
  )
}
