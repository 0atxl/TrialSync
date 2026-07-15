import type { ScreeningState } from '../api/client'
import { stateLabel } from '../pages/screeningHelpers'

type Distribution = Record<ScreeningState, number>
export function StateDistribution({ counts, label }: { counts: Distribution; label: string }) {
  const entries = Object.entries(counts) as Array<[ScreeningState, number]>
  const total = entries.reduce((sum, [, count]) => sum + count, 0)
  return <section className="distribution" aria-label={label}><div className="distribution-bar" role="img" aria-label={entries.map(([state, count]) => `${stateLabel(state)} ${count}`).join(', ')}>{entries.map(([state, count]) => count > 0 && <span className={`distribution-segment distribution-${state}`} style={{ width: `${count / total * 100}%` }} key={state} />)}</div><div className="distribution-legend">{entries.map(([state, count]) => <span key={state}><i className={`legend-dot legend-${state}`} aria-hidden="true" /><strong>{count}</strong> {stateLabel(state)}</span>)}</div>{total === 0 && <p>No screening results to visualize yet.</p>}</section>
}
