import { Link } from 'react-router-dom'

import type {
  OverviewActivityPoint,
  OverviewDropoutState,
  ScreeningState,
} from '../api/client'
import { stateLabel } from '../pages/screeningHelpers'

const eligibilityOrder: ScreeningState[] = [
  'potentially_eligible',
  'needs_review',
  'likely_ineligible',
]

export function EligibilityOverviewChart({
  counts,
}: {
  counts: Record<ScreeningState, number> & { total: number }
}) {
  const total = Math.max(1, counts.total)
  return (
    <div className="overview-eligibility-chart" aria-label="Eligibility distribution">
      <div className="overview-stacked-bar">
        {eligibilityOrder.map((state) => counts[state] > 0 ? (
          <Link
            className={`overview-eligibility-segment overview-eligibility-${state}`}
            aria-label={`${counts[state]} ${stateLabel(state)} screenings`}
            style={{ width: `${counts[state] / total * 100}%` }}
            to={`/screenings?result=${state}`}
            key={state}
          />
        ) : null)}
      </div>
      <div className="overview-eligibility-legend">
        {eligibilityOrder.map((state) => (
          <Link to={`/screenings?result=${state}`} key={state}>
            <i className={`overview-dot overview-dot-${state}`} aria-hidden="true" />
            <span>{stateLabel(state)}</span>
            <strong>{counts[state]}</strong>
          </Link>
        ))}
      </div>
    </div>
  )
}

type ActivityBucket = {
  from: string
  to: string
  count: number
}

function weeklyBuckets(points: OverviewActivityPoint[]): ActivityBucket[] {
  const buckets: ActivityBucket[] = []
  for (let index = 0; index < points.length; index += 7) {
    const week = points.slice(index, index + 7)
    if (!week.length) continue
    buckets.push({
      from: week[0].date,
      to: week.at(-1)?.date ?? week[0].date,
      count: week.reduce((sum, point) => sum + point.count, 0),
    })
  }
  return buckets
}

const shortDate = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', timeZone: 'UTC' })

function dateLabel(value: string) {
  return shortDate.format(new Date(`${value}T00:00:00Z`))
}

export function ScreeningActivityChart({ points }: { points: OverviewActivityPoint[] }) {
  const buckets = weeklyBuckets(points)
  const maximum = Math.max(1, ...buckets.map((bucket) => bucket.count))
  const total = buckets.reduce((sum, bucket) => sum + bucket.count, 0)
  return (
    <div className="overview-activity-chart">
      <div className="overview-activity-bars" aria-label={`${total} screenings during the last eight weeks`}>
        {buckets.map((bucket) => (
          <Link
            aria-label={`${bucket.count} screenings from ${dateLabel(bucket.from)} to ${dateLabel(bucket.to)}`}
            to={`/screenings?from=${bucket.from}&to=${bucket.to}`}
            title={`${bucket.count} screenings · ${dateLabel(bucket.from)}–${dateLabel(bucket.to)}`}
            key={bucket.from}
          >
            <span style={{ height: `${Math.max(bucket.count ? 9 : 2, bucket.count / maximum * 100)}%` }} />
            <small>{dateLabel(bucket.from)}</small>
          </Link>
        ))}
      </div>
    </div>
  )
}

const dropoutLabels: Record<OverviewDropoutState, string> = {
  not_started: 'Not started',
  information_needed: 'Information needed',
  ready: 'Ready',
  predicted: 'Estimate available',
}

const dropoutOrder: OverviewDropoutState[] = [
  'not_started',
  'information_needed',
  'ready',
  'predicted',
]

export function DropoutWorkflowChart({
  counts,
  total,
}: {
  counts: Record<OverviewDropoutState, number>
  total: number
}) {
  const safeTotal = Math.max(1, total)
  return (
    <div className="overview-dropout-chart" aria-label="Dropout workflow distribution">
      <div className="overview-dropout-track" aria-hidden="true">
        {dropoutOrder.map((state) => counts[state] > 0 ? (
          <span
            className={`overview-dropout-${state}`}
            style={{ width: `${counts[state] / safeTotal * 100}%` }}
            key={state}
          />
        ) : null)}
      </div>
      <div className="overview-dropout-steps">
        {dropoutOrder.map((state) => (
          <Link to={`/research/dropout?status=${state}`} key={state}>
            <span>{dropoutLabels[state]}</span>
            <strong>{counts[state]}</strong>
          </Link>
        ))}
      </div>
    </div>
  )
}
