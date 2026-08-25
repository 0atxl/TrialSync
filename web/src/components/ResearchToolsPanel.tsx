import { useState } from 'react'
import { Activity, Network, UsersRound } from 'lucide-react'
import { Link } from 'react-router-dom'

import {
  ApiError,
  apiRequest,
  type CohortContext,
  type ResearchRepresentation,
  type Screening,
  type ScreeningSimilarity,
} from '../api/client'
import { ResearchRiskPanel } from './ResearchRiskPanel'

type ToolName = 'risk' | 'cohort' | 'similarity'

const representationLabel: Record<ResearchRepresentation, string> = {
  patient_fact: 'Recorded facts',
  screening_profile: 'Eligibility evidence patterns',
}

function readableFeature(value: string) {
  return value
    .replace(/^criterion:[^:]+:[^:]+:/, '')
    .replaceAll('_', ' ')
    .replaceAll(':', ' · ')
}

function requestMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback
}

export function ResearchToolsPanel({ screening, token }: { screening: Screening; token: string | null }) {
  const [active, setActive] = useState<ToolName | null>(null)
  const [representation, setRepresentation] = useState<ResearchRepresentation>('patient_fact')
  const [cohort, setCohort] = useState<CohortContext | null>(null)
  const [similarity, setSimilarity] = useState<ScreeningSimilarity | null>(null)
  const [loading, setLoading] = useState<ToolName | null>(null)
  const [error, setError] = useState('')

  const open = async (tool: ToolName) => {
    setActive(tool)
    setError('')
    if (tool === 'risk') return
    setLoading(tool)
    try {
      if (tool === 'cohort') {
        setCohort(await apiRequest<CohortContext>(
          `/research/screenings/${screening.id}/cohort-context`,
          { method: 'POST', body: JSON.stringify({ representation }) },
          token,
        ))
      } else {
        setSimilarity(await apiRequest<ScreeningSimilarity>(
          `/research/screenings/${screening.id}/similarity`,
          { method: 'POST', body: JSON.stringify({ representation, neighbor_count: 5 }) },
          token,
        ))
      }
    } catch (caught) {
      setError(requestMessage(caught, 'This research view could not be loaded.'))
    } finally {
      setLoading(null)
    }
  }

  const switchRepresentation = async (value: ResearchRepresentation) => {
    setRepresentation(value)
    setCohort(null)
    setSimilarity(null)
    if (active) await openWithRepresentation(active, value)
  }

  const openWithRepresentation = async (tool: ToolName, value: ResearchRepresentation) => {
    if (tool === 'risk') return
    setError('')
    setLoading(tool)
    try {
      if (tool === 'cohort') {
        setCohort(await apiRequest<CohortContext>(
          `/research/screenings/${screening.id}/cohort-context`,
          { method: 'POST', body: JSON.stringify({ representation: value }) }, token,
        ))
      } else {
        setSimilarity(await apiRequest<ScreeningSimilarity>(
          `/research/screenings/${screening.id}/similarity`,
          { method: 'POST', body: JSON.stringify({ representation: value, neighbor_count: 5 }) }, token,
        ))
      }
    } catch (caught) {
      setError(requestMessage(caught, 'This research view could not be loaded.'))
    } finally {
      setLoading(null)
    }
  }

  return <section className="research-tools research-tools-compact" aria-labelledby="research-tools-title">
    <div className="research-heading">
      <h2 id="research-tools-title">Research</h2>
      <p>These views do not change eligibility.</p>
    </div>
    <div className="research-tool-actions">
      <button
        className={active === 'risk' ? 'research-action active' : 'research-action'}
        type="button"
        aria-label="Predict dropout risk"
        aria-expanded={active === 'risk'}
        onClick={() => { void open('risk') }}
      >
        <Activity aria-hidden="true" size={19} />
        <span><strong>Predict dropout risk</strong><small>Add follow-up information</small></span>
      </button>
      <button
        className={active === 'cohort' ? 'research-action active' : 'research-action'}
        type="button"
        aria-label="View cohort context"
        aria-expanded={active === 'cohort'}
        onClick={() => { void open('cohort') }}
      >
        <Network aria-hidden="true" size={19} />
        <span><strong>{loading === 'cohort' ? 'Loading context…' : 'View cohort context'}</strong><small>See this participant on the map</small></span>
      </button>
      <button
        className={active === 'similarity' ? 'research-action active' : 'research-action'}
        type="button"
        aria-label="Find similar participants"
        aria-expanded={active === 'similarity'}
        onClick={() => { void open('similarity') }}
      >
        <UsersRound aria-hidden="true" size={19} />
        <span><strong>{loading === 'similarity' ? 'Finding participants…' : 'Find similar participants'}</strong><small>Compare recorded profiles</small></span>
      </button>
    </div>

    {active === 'risk' && <ResearchRiskPanel screening={screening} token={token} />}
    {(active === 'cohort' || active === 'similarity') && <div className="research-detail-panel">
      <div className="research-detail-head">
        <div><p className="eyebrow">Frozen representation</p><h3>{active === 'cohort' ? 'Projected cohort context' : 'Exact reference neighbors'}</h3></div>
        <label>Compare using<select value={representation} onChange={(event) => { void switchRepresentation(event.target.value as ResearchRepresentation) }}><option value="patient_fact">Recorded facts</option><option value="screening_profile">Eligibility evidence patterns</option></select></label>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      {loading === active && <div className="research-loading">Building the frozen {representationLabel[representation].toLowerCase()} projection…</div>}
      {active === 'cohort' && cohort && <CohortResult context={cohort} screeningId={screening.id} />}
      {active === 'similarity' && similarity && <SimilarityResult result={similarity} screeningId={screening.id} />}
    </div>}
  </section>
}

function CohortResult({ context, screeningId }: { context: CohortContext; screeningId: string }) {
  const association = context.association
  return <div className="cohort-result">
    <div className="cohort-placement">
      <div className={association.is_unassigned ? 'cohort-orbit unassigned' : 'cohort-orbit'} aria-hidden="true"><span /></div>
      <div><p className="eyebrow">Out-of-sample overlay</p><h4>{association.is_unassigned ? 'No dense-group association' : association.cluster_label?.replaceAll('_', ' ')}</h4><p>{association.is_unassigned ? 'No frozen DBSCAN core member is within this run’s association radius. This is the explicit unassigned state.' : `The nearest frozen core member is within the run’s ${association.eps.toFixed(3)} radius. This is an association for a new point, not membership in the original fit.`}</p></div>
    </div>
    <dl className="research-metadata"><div><dt>Representation</dt><dd>{representationLabel[context.representation]}</dd></div><div><dt>Nearest core distance</dt><dd>{association.nearest_core_distance == null ? 'Not within radius' : association.nearest_core_distance.toFixed(4)}</dd></div><div><dt>PCA overlay</dt><dd>{context.projection.x.toFixed(2)}, {context.projection.y.toFixed(2)} <small>display only</small></dd></div><div><dt>Reference run</dt><dd>{context.run_id}</dd></div></dl>
    {association.competing_labels.length > 1 && <p className="research-note">Nearby core points span {association.competing_labels.length} groups; the nearest core point resolves the association deterministically.</p>}
    {context.unsupported_concepts.length > 0 && <p className="research-note">Outside this frozen representation: {context.unsupported_concepts.join(', ')}.</p>}
    <p className="research-boundary">Exploratory generated-cohort context only. A DBSCAN association is not a diagnosis, phenotype, priority score, or eligibility result.</p>
    <Link className="secondary-button research-atlas-link" to={`/research/cohorts?screening=${screeningId}&representation=${context.representation}&tool=cohort`}>Open this overlay in Cohort Atlas</Link>
  </div>
}

function SimilarityResult({ result, screeningId }: { result: ScreeningSimilarity; screeningId: string }) {
  return <div className="similarity-result">
    <div className="similarity-summary"><strong>{result.neighbors.length}</strong><span>exact neighbors in {representationLabel[result.representation].toLowerCase()}</span><small>{result.index_metadata.index_type} · {result.index_metadata.vector_count} reference vectors</small></div>
    <ol className="neighbor-list">{result.neighbors.map((neighbor) => <li key={neighbor.member_id}>
      <details open={neighbor.rank === 1}><summary><span className="neighbor-rank">{String(neighbor.rank).padStart(2, '0')}</span><span><strong>{neighbor.label}</strong><small>{neighbor.member_id}</small></span><span className="cosine-score">{neighbor.cosine_similarity.toFixed(3)}<small>cosine</small></span></summary>
        <div className="difference-table" role="table" aria-label={`Feature differences for ${neighbor.label}`}>
          {neighbor.feature_differences.slice(0, 6).map((difference) => <div role="row" key={`${neighbor.member_id}-${difference.feature}`}>
            <span role="cell"><strong>{difference.criterion_context?.criterion_text ?? readableFeature(difference.feature)}</strong>{difference.criterion_context && <small>{difference.criterion_context.trial_label} · query {difference.criterion_context.query_result}</small>}</span>
            <span role="cell">This screening <strong>{difference.query_value ?? 'missing'}</strong></span><span role="cell">Neighbor <strong>{difference.neighbor_value ?? 'missing'}</strong></span>
          </div>)}
        </div>
      </details>
    </li>)}</ol>
    {result.unsupported_concepts.length > 0 && <p className="research-note">Outside this frozen representation: {result.unsupported_concepts.join(', ')}.</p>}
    <p className="research-boundary">Exact cosine similarity describes closeness in one frozen generated feature space. It is not screening evidence, a clinical recommendation, or a predicted outcome.</p>
    <Link className="secondary-button research-atlas-link" to={`/research/cohorts?screening=${screeningId}&representation=${result.representation}&tool=similarity`}>Inspect these neighbors in Cohort Atlas</Link>
  </div>
}
