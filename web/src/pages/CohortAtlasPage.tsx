import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  ApiError,
  apiRequest,
  type CohortClusters,
  type CohortContext,
  type CohortMemberDetail,
  type CohortMembers,
  type CohortPoint,
  type CohortRuns,
  type CohortSimilarity,
  type ResearchRepresentation,
  type ScreeningSimilarity,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ResearchNav } from '../components/ResearchNav'

const representationLabels = { patient_fact: 'Recorded facts', screening_profile: 'Eligibility evidence patterns' }
const clusterPalette = ['#2d6d73', '#a7783e', '#755f8f', '#4f7d5d', '#a15f68', '#507394']

function errorMessage(error: unknown, fallback: string) { return error instanceof ApiError || error instanceof Error ? error.message : fallback }
function featureLabel(value: string) { return value.replaceAll(':', ' · ').replaceAll('_', ' ') }

export function CohortAtlasPage() {
  const { token } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const screeningId = searchParams.get('screening')
  const requestedTool = searchParams.get('tool')
  const requestedRepresentation = searchParams.get('representation')
  const [representation, setRepresentation] = useState<ResearchRepresentation>(requestedRepresentation === 'screening_profile' ? 'screening_profile' : 'patient_fact')
  const [runs, setRuns] = useState<CohortRuns | null>(null)
  const [clusters, setClusters] = useState<CohortClusters | null>(null)
  const [members, setMembers] = useState<CohortMembers | null>(null)
  const [clusterFilter, setClusterFilter] = useState('all')
  const [selected, setSelected] = useState<CohortMemberDetail | null>(null)
  const [neighbors, setNeighbors] = useState<CohortSimilarity | null>(null)
  const [externalContext, setExternalContext] = useState<CohortContext | null>(null)
  const [externalNeighbors, setExternalNeighbors] = useState<ScreeningSimilarity | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError(''); setSelected(null); setNeighbors(null)
    try {
      const runResponse = await apiRequest<CohortRuns>('/research/cohorts/runs', {}, token)
      setRuns(runResponse)
      if (!runResponse.active_run_id || runResponse.status !== 'ready') throw new Error(runResponse.message ?? 'The active cohort run is unavailable.')
      const query = new URLSearchParams({ representation, limit: '50' })
      if (clusterFilter === 'noise') query.set('noise', 'true')
      else if (clusterFilter !== 'all') query.set('cluster_label', clusterFilter)
      const [clusterResponse, memberResponse] = await Promise.all([
        apiRequest<CohortClusters>(`/research/cohorts/runs/${runResponse.active_run_id}/clusters?representation=${representation}`, {}, token),
        apiRequest<CohortMembers>(`/research/cohorts/runs/${runResponse.active_run_id}/members?${query}`, {}, token),
      ])
      setClusters(clusterResponse); setMembers(memberResponse)
      if (screeningId) {
        const wantsContext = requestedTool !== 'similarity'
        const wantsNeighbors = requestedTool !== 'cohort'
        const [contextResponse, neighborResponse] = await Promise.all([
          wantsContext ? apiRequest<CohortContext>(`/research/screenings/${screeningId}/cohort-context`, { method: 'POST', body: JSON.stringify({ representation }) }, token) : Promise.resolve(null),
          wantsNeighbors ? apiRequest<ScreeningSimilarity>(`/research/screenings/${screeningId}/similarity`, { method: 'POST', body: JSON.stringify({ representation, neighbor_count: 5 }) }, token) : Promise.resolve(null),
        ])
        setExternalContext(contextResponse); setExternalNeighbors(neighborResponse)
      } else { setExternalContext(null); setExternalNeighbors(null) }
    } catch (caught) { setError(errorMessage(caught, 'The Cohort Atlas could not be loaded.')) }
    finally { setLoading(false) }
  }, [clusterFilter, representation, requestedTool, screeningId, token])
  useEffect(() => { void load() }, [load])

  const selectMember = async (member: CohortPoint) => {
    if (!runs?.active_run_id) return
    setDetailLoading(true); setError('')
    try {
      const [detail, similar] = await Promise.all([
        apiRequest<CohortMemberDetail>(`/research/cohorts/runs/${runs.active_run_id}/members/${member.member_id}`, {}, token),
        apiRequest<CohortSimilarity>('/research/similarity/queries', { method: 'POST', body: JSON.stringify({ run_id: runs.active_run_id, representation, member_id: member.member_id, neighbor_count: 5 }) }, token),
      ])
      setSelected(detail); setNeighbors(similar)
    } catch (caught) { setError(errorMessage(caught, 'Participant context could not be loaded.')) }
    finally { setDetailLoading(false) }
  }

  const changeRepresentation = (next: ResearchRepresentation) => {
    setRepresentation(next); setClusterFilter('all')
    const updated = new URLSearchParams(searchParams); updated.set('representation', next); setSearchParams(updated, { replace: true })
  }

  return <section className="route-entry workspace-page research-page atlas-page">
    <ResearchNav />
    <header className="page-heading research-page-heading"><h1>Cohort Atlas</h1><label className="atlas-representation">View<select value={representation} onChange={(event) => changeRepresentation(event.target.value as ResearchRepresentation)}><option value="patient_fact">Recorded facts</option><option value="screening_profile">Eligibility evidence patterns</option></select></label></header>
    <p className="research-boundary overview-boundary">PCA coordinates are display-only. DBSCAN association and exact cosine similarity use the complete frozen feature vectors and never change eligibility.</p>
    {error && <div className="form-error atlas-error" role="alert">{error}<button className="text-button" type="button" onClick={() => { void load() }}>Retry</button></div>}
    {loading ? <div className="loading-state">Loading the active reference landscape…</div> : clusters && members && runs?.active_run_id ? <>
      <section className="atlas-summary"><div><span>Reference members</span><strong>{clusters.points.length}</strong></div><div><span>Dense groups</span><strong>{clusters.cluster_count}</strong></div><div><span>Noise</span><strong>{(clusters.noise_fraction * 100).toFixed(0)}%</strong></div><div><span>DBSCAN parameters</span><strong>ε {clusters.selected_parameters.eps} · min {clusters.selected_parameters.min_samples}</strong></div><div><span>Exact index</span><strong>CPU cosine</strong></div></section>
      {externalContext && <ExternalOverlay context={externalContext} screeningId={screeningId!} onClose={() => { const next = new URLSearchParams(searchParams); next.delete('screening'); next.delete('tool'); setSearchParams(next, { replace: true }) }} />}
      <div className="atlas-layout">
        <section className="atlas-map-panel"><div className="atlas-panel-head"><div><p className="eyebrow">Seeded PCA projection</p><h2>{representationLabels[representation]}</h2></div><label>Show<select value={clusterFilter} onChange={(event) => setClusterFilter(event.target.value)}><option value="all">All members</option>{clusters.clusters.map((cluster) => <option key={cluster.label} value={cluster.label}>{cluster.label.replaceAll('_', ' ')} · {cluster.size}</option>)}<option value="noise">Noise only</option></select></label></div><AtlasPlot clusters={clusters} clusterFilter={clusterFilter} selectedId={selected?.member_id ?? null} external={externalContext} onSelect={(point) => { void selectMember(point) }} /><AtlasLegend clusters={clusters} /></section>
        <aside className="atlas-inspector" aria-live="polite">{detailLoading ? <div className="research-loading">Loading exact participant comparison…</div> : selected && neighbors ? <MemberInspector member={selected} representation={representation} neighbors={neighbors.neighbors} /> : externalNeighbors ? <ExternalNeighborInspector result={externalNeighbors} /> : <div className="atlas-inspector-empty"><p className="eyebrow">Participant inspection</p><h2>Select a reference member</h2><p>Use the structured list below or choose a point to inspect both representation assignments and exact nearest neighbors.</p></div>}</aside>
      </div>
      <MemberTable members={members} selectedId={selected?.member_id ?? null} onSelect={(member) => { void selectMember(member) }} />
      <footer className="overview-model-line"><span>Active run {runs.active_run_id}</span><span>{clusters.representation_version}</span><span>{clusters.display_projection_only ? '2D display projection only' : ''}</span></footer>
    </> : !error && <div className="empty-state"><h2>No active cohort run</h2><p>Configure and verify an accepted generated reference run before opening the Atlas.</p></div>}
  </section>
}

function AtlasPlot({ clusters, clusterFilter, selectedId, external, onSelect }: { clusters: CohortClusters; clusterFilter: string; selectedId: string | null; external: CohortContext | null; onSelect: (point: CohortPoint) => void }) {
  const visiblePoints = clusters.points.filter((point) => clusterFilter === 'all' || (clusterFilter === 'noise' ? point.is_noise : point.cluster_label === clusterFilter))
  const allX = clusters.points.map((point) => point.x).concat(external ? [external.projection.x] : [])
  const allY = clusters.points.map((point) => point.y).concat(external ? [external.projection.y] : [])
  const minX = Math.min(...allX); const maxX = Math.max(...allX); const minY = Math.min(...allY); const maxY = Math.max(...allY)
  const x = (value: number) => 24 + (value - minX) / Math.max(.0001, maxX - minX) * 652
  const y = (value: number) => 376 - (value - minY) / Math.max(.0001, maxY - minY) * 352
  const labels = clusters.clusters.map((cluster) => cluster.label)
  const color = (point: CohortPoint) => point.is_noise ? '#aab2b2' : clusterPalette[Math.max(0, labels.indexOf(point.cluster_label ?? '')) % clusterPalette.length]
  return <svg className="atlas-plot" viewBox="0 0 700 400" role="img" aria-label={`PCA display projection of ${visiblePoints.length} generated reference participants`}>
    <rect x="0" y="0" width="700" height="400" rx="6" />
    <path d="M24 200H676M350 24V376" />
    {visiblePoints.map((point) => <circle key={point.member_id} cx={x(point.x)} cy={y(point.y)} r={point.member_id === selectedId ? 6 : point.is_noise ? 2.1 : 2.7} fill={color(point)} className={point.member_id === selectedId ? 'selected' : ''} onClick={() => onSelect(point)}><title>{point.label} · {point.cluster_label ?? 'noise'}</title></circle>)}
    {external && <g className="external-marker" transform={`translate(${x(external.projection.x)} ${y(external.projection.y)})`}><circle r="10" /><path d="M-5 0H5M0-5V5" /></g>}
  </svg>
}

function AtlasLegend({ clusters }: { clusters: CohortClusters }) { return <div className="atlas-legend">{clusters.clusters.map((cluster, index) => <span key={cluster.label}><i style={{ background: clusterPalette[index % clusterPalette.length] }} />{cluster.label.replaceAll('_', ' ')} <strong>{cluster.size}</strong></span>)}<span><i className="noise" />noise <strong>{Math.round(clusters.noise_fraction * clusters.points.length)}</strong></span></div> }

function ExternalOverlay({ context, screeningId, onClose }: { context: CohortContext; screeningId: string; onClose: () => void }) { return <section className="external-overlay"><div><p className="eyebrow">Saved-screening overlay</p><h2>{context.association.is_unassigned ? 'Unassigned under the frozen core-radius rule' : context.association.cluster_label?.replaceAll('_', ' ')}</h2><p>Screening {screeningId} is shown as an external marker. It was not inserted into the 750-member reference run.</p></div><dl><div><dt>Nearest core</dt><dd>{context.association.nearest_core_distance?.toFixed(4) ?? 'Outside radius'}</dd></div><div><dt>Representation</dt><dd>{representationLabels[context.representation]}</dd></div></dl><button className="text-button" type="button" onClick={onClose}>Remove overlay</button></section> }

function MemberTable({ members, selectedId, onSelect }: { members: CohortMembers; selectedId: string | null; onSelect: (point: CohortPoint) => void }) { return <section className="atlas-table-section"><div className="section-heading"><div><p className="eyebrow">Structured reference list</p><h2>{members.total} matching members</h2></div><span>Showing {members.members.length}</span></div><div className="atlas-member-table" aria-label="Reference cohort members"><div className="atlas-table-head"><span>Participant</span><span>Recorded context</span><span>DBSCAN state</span><span>PCA coordinates</span></div>{members.members.map((member) => <button type="button" aria-label={`Inspect ${member.label}`} className={member.member_id === selectedId ? 'selected' : ''} key={member.member_id} onClick={() => onSelect(member)}><span><strong>{member.label}</strong><small>{member.member_id}</small></span><span>{member.conditions.join(', ') || 'No condition assertion'}<small>{member.sex} · born {member.date_of_birth}</small></span><span>{member.is_noise ? 'Noise' : member.cluster_label?.replaceAll('_', ' ')}</span><span>{member.x.toFixed(2)}, {member.y.toFixed(2)}</span></button>)}</div></section> }

function MemberInspector({ member, representation, neighbors }: { member: CohortMemberDetail; representation: ResearchRepresentation; neighbors: CohortSimilarity['neighbors'] }) { const state = member.representations[representation]; return <div><p className="eyebrow">Selected reference member</p><h2>{member.label}</h2><p className="inspector-id">{member.member_id}</p><dl className="inspector-facts"><div><dt>Recorded conditions</dt><dd>{member.conditions.join(', ') || 'None recorded'}</dd></div><div><dt>Fact-space state</dt><dd>{member.representations.patient_fact.is_noise ? 'Noise' : member.representations.patient_fact.cluster_label}</dd></div><div><dt>Evidence-pattern state</dt><dd>{member.representations.screening_profile.is_noise ? 'Noise' : member.representations.screening_profile.cluster_label}</dd></div><div><dt>Current PCA position</dt><dd>{state.x.toFixed(2)}, {state.y.toFixed(2)}</dd></div></dl><NeighborList neighbors={neighbors} /><p className="research-boundary">Exact neighbors are navigation aids, not eligibility evidence or recommendations.</p></div> }

function ExternalNeighborInspector({ result }: { result: ScreeningSimilarity }) { return <div><p className="eyebrow">External screening query</p><h2>Closest reference records</h2><p className="inspector-id">Exact cosine search · {result.index_metadata.index_type}</p><NeighborList neighbors={result.neighbors} /><p className="research-boundary">The saved screening remains outside the reference cohort. Similarity cannot change its eligibility result.</p></div> }

function NeighborList({ neighbors }: { neighbors: CohortSimilarity['neighbors'] }) { return <ol className="atlas-neighbors">{neighbors.map((neighbor) => <li key={neighbor.member_id}><details><summary><span>{neighbor.rank}</span><span><strong>{neighbor.label}</strong><small>{neighbor.member_id}</small></span><b>{neighbor.cosine_similarity.toFixed(3)}</b></summary><div>{neighbor.feature_differences.slice(0, 4).map((difference) => <p key={difference.feature}><span>{difference.criterion_context?.criterion_text ?? featureLabel(difference.feature)}</span><small>{difference.query_value ?? 'missing'} → {difference.neighbor_value ?? 'missing'}</small></p>)}</div></details></li>)}</ol> }
