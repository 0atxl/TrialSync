import { AlertCircle, ArrowUpRight, CalendarClock, CheckCircle2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  apiRequest,
  type Overview,
  type OverviewAttentionItem,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import {
  DropoutWorkflowChart,
  EligibilityOverviewChart,
  ScreeningActivityChart,
} from '../components/OverviewCharts'
import { StateMessage } from '../components/UiPrimitives'
import { stateLabel } from './screeningHelpers'

const attentionLabels: Record<OverviewAttentionItem['kind'], string> = {
  eligibility_review: 'Needs review',
  dropout_not_started: 'Start dropout follow-up',
  dropout_information_needed: 'Complete day-30 information',
  dropout_ready: 'Dropout estimate is ready',
}

const shortDate = new Intl.DateTimeFormat('en', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})

function formatDate(value: string) {
  return shortDate.format(new Date(`${value}T00:00:00Z`))
}

function attentionDestination(item: OverviewAttentionItem) {
  return item.kind === 'eligibility_review'
    ? `/screenings/${item.screening_id}`
    : `/screenings/${item.screening_id}?research=dropout`
}

function DashboardSkeleton() {
  return (
    <div className="overview-skeleton" aria-label="Loading overview" role="status">
      <span className="overview-skeleton-wide" />
      <span />
      <span />
      <span />
      <span />
    </div>
  )
}

export function DashboardPage() {
  const { token } = useAuth()
  const [overview, setOverview] = useState<Overview | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setOverview(await apiRequest('/overview', {}, token))
      setError('')
    } catch {
      setError('Dashboard data could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  return (
    <section className="route-entry workspace-page overview-page">
      <h1 className="visually-hidden">Dashboard</h1>
      {loading ? <DashboardSkeleton /> : error ? (
        <StateMessage
          state="error"
          title="Dashboard unavailable"
          action={<button className="secondary-button" type="button" onClick={() => void load()}>Retry</button>}
        >
          <p>{error}</p>
        </StateMessage>
      ) : !overview || overview.eligibility.total === 0 ? (
        <StateMessage
          state="empty"
          title="No screening activity yet"
          action={<Link className="secondary-button" to="/screenings">Open screenings</Link>}
        >
          <p>Saved screening results and follow-up activity will appear here.</p>
        </StateMessage>
      ) : (
        <div className="overview-dashboard">
          <section className="overview-section overview-eligibility-section">
            <header className="overview-section-head">
              <div>
                <span>Eligibility</span>
                <h2><strong>{overview.eligibility.total}</strong> saved screenings</h2>
              </div>
              <Link className="overview-section-link" to="/screenings">View screenings <ArrowUpRight size={15} aria-hidden="true" /></Link>
            </header>
            <EligibilityOverviewChart counts={overview.eligibility} />
          </section>

          <div className="overview-analytics-grid">
            <section className="overview-section">
              <header className="overview-section-head">
                <div>
                  <span>Activity</span>
                  <h2>Last 8 weeks</h2>
                </div>
                <CalendarClock size={20} aria-hidden="true" />
              </header>
              <ScreeningActivityChart points={overview.activity} />
            </section>

            <section className="overview-section">
              <header className="overview-section-head">
                <div>
                  <span>Dropout follow-up</span>
                  <h2>{overview.dropout.eligible_total} eligible screenings</h2>
                </div>
                <Link className="overview-section-link" to="/research/dropout">Open dashboard <ArrowUpRight size={15} aria-hidden="true" /></Link>
              </header>
              <DropoutWorkflowChart counts={overview.dropout.counts} total={overview.dropout.eligible_total} />
              {overview.dropout.status === 'degraded' ? (
                <p className="overview-degraded-note"><AlertCircle size={15} aria-hidden="true" />{overview.dropout.message}</p>
              ) : null}
            </section>
          </div>

          <div className="overview-lists-grid">
            <section className="overview-section overview-list-section">
              <header className="overview-section-head">
                <div>
                  <span>Needs attention</span>
                  <h2>{overview.attention.length ? `${overview.attention.length} ${overview.attention.length === 1 ? 'item' : 'items'}` : 'All caught up'}</h2>
                </div>
                {overview.attention.length ? <AlertCircle size={20} aria-hidden="true" /> : <CheckCircle2 size={20} aria-hidden="true" />}
              </header>
              {overview.attention.length ? (
                <div className="overview-record-list">
                  {overview.attention.map((item) => (
                    <Link className="overview-record-row" to={attentionDestination(item)} key={`${item.kind}-${item.screening_id}`}>
                      <div>
                        <strong>{item.patient_name}</strong>
                        <small>{item.trial_title}</small>
                      </div>
                      <span>{attentionLabels[item.kind]}</span>
                      <ArrowUpRight size={15} aria-hidden="true" />
                    </Link>
                  ))}
                </div>
              ) : <p className="overview-quiet-state">There are no unresolved screening or follow-up items.</p>}
            </section>

            <section className="overview-section overview-list-section">
              <header className="overview-section-head">
                <div>
                  <span>Recent</span>
                  <h2>Saved screenings</h2>
                </div>
                <Link className="overview-section-link" to="/screenings">View all <ArrowUpRight size={15} aria-hidden="true" /></Link>
              </header>
              <div className="overview-record-list">
                {overview.recent_screenings.map((item) => (
                  <Link className="overview-record-row overview-recent-row" to={`/screenings/${item.screening_id}`} key={item.screening_id}>
                    <div>
                      <strong>{item.patient_name}</strong>
                      <small>{item.trial_title}</small>
                    </div>
                    <span className={`state state-${item.overall_state}`}>{stateLabel(item.overall_state)}</span>
                    <time dateTime={item.screening_date}>{formatDate(item.screening_date)}</time>
                    <ArrowUpRight size={15} aria-hidden="true" />
                  </Link>
                ))}
              </div>
            </section>
          </div>
        </div>
      )}
    </section>
  )
}
