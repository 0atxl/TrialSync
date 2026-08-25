import { useCallback, useEffect, useMemo, useState } from 'react'

import { apiRequest, type TrialResearchOverview } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ResearchNav } from '../components/ResearchNav'
import { StateDistribution } from '../components/StateDistribution'

const bandLabels = { lower: 'Lower model band', near_threshold: 'Near threshold', higher: 'Higher model band' }

export function RecruitmentOverviewPage() {
  const { token } = useAuth()
  const [overviews, setOverviews] = useState<TrialResearchOverview[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const next = await apiRequest<TrialResearchOverview[]>('/research/trial-overview', {}, token)
      setOverviews(next)
      setSelectedId((current) => next.some((item) => item.trial_version_id === current) ? current : next[0]?.trial_version_id ?? '')
      setError('')
    } catch { setError('The recruitment overview could not be loaded.') }
    finally { setLoading(false) }
  }, [token])
  useEffect(() => { void load() }, [load])

  const selected = useMemo(() => overviews.find((item) => item.trial_version_id === selectedId) ?? null, [overviews, selectedId])
  return <section className="route-entry workspace-page research-page">
    <ResearchNav />
    <header className="page-heading research-page-heading"><div><p className="eyebrow">Research workspace</p><h1>Recruitment overview</h1><p>Compare deterministic screening totals with explicitly linked day-30 retention predictions.</p></div>{overviews.length > 0 && <label className="research-trial-selector">Approved trial version<select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{overviews.map((item) => <option key={item.trial_version_id} value={item.trial_version_id}>{item.trial.title} · v{item.trial.version}</option>)}</select></label>}</header>
    <p className="research-boundary overview-boundary">Eligibility totals and dropout-risk bands answer different questions. This view never turns a retention prediction into a screening result.</p>
    {error ? <div className="form-error" role="alert">{error}<button className="text-button" type="button" onClick={() => { void load() }}>Retry</button></div> : loading ? <div className="loading-state">Loading approved trial versions and linked predictions…</div> : !selected ? <div className="empty-state"><h2>No saved screening results</h2><p>Run and save a deterministic screening before using the trial-level research overview.</p></div> : <RecruitmentDetail overview={selected} />}
  </section>
}

function RecruitmentDetail({ overview }: { overview: TrialResearchOverview }) {
  const { trial, screening_counts: screeningCounts, retention } = overview
  const total = Object.values(screeningCounts).reduce((sum, count) => sum + count, 0)
  const linkedPercent = retention.eligible_total ? retention.linked_predictions / retention.eligible_total * 100 : 0
  return <div className="recruitment-detail">
    <section className="recruitment-trial-head"><div><p className="eyebrow">{trial.registry_id} · approved v{trial.version}</p><h2>{trial.title}</h2></div><div><strong>{total}</strong><span>saved screenings</span></div></section>
    <div className="recruitment-split">
      <section className="eligibility-overview"><div className="section-heading"><div><p className="eyebrow">Authoritative result</p><h2>Deterministic eligibility</h2></div></div><StateDistribution counts={screeningCounts} label={`Eligibility distribution for ${trial.title}`} /><dl className="overview-ledger"><div><dt>Potentially eligible</dt><dd>{screeningCounts.potentially_eligible}</dd></div><div><dt>Needs review</dt><dd>{screeningCounts.needs_review}</dd></div><div><dt>Likely ineligible</dt><dd>{screeningCounts.likely_ineligible}</dd></div></dl></section>
      <section className="retention-overview"><div className="section-heading"><div><p className="eyebrow">Separate research signal</p><h2>Linked retention predictions</h2></div><span className="linked-ratio">{retention.linked_predictions}/{retention.eligible_total}</span></div>
        <div className="linkage-meter" aria-label={`${retention.linked_predictions} of ${retention.eligible_total} potentially eligible screenings have predictions`}><div style={{ width: `${linkedPercent}%` }} /></div><p className="linkage-copy"><strong>{retention.linked_predictions}</strong> linked predictions · <strong>{retention.unlinked_eligible}</strong> potentially eligible screenings without a prediction</p>
        <div className="risk-band-chart">{Object.entries(retention.risk_bands).map(([band, count]) => { const denominator = Math.max(1, retention.linked_predictions); return <div key={band}><span>{bandLabels[band as keyof typeof bandLabels]}</span><div><i style={{ width: `${count / denominator * 100}%` }} /></div><strong>{count}</strong></div> })}</div>
        {retention.linked_predictions === 0 && <div className="research-note overview-empty-note">No linked predictions yet. Eligibility totals remain complete and visible.</div>}
      </section>
    </div>
    <footer className="overview-model-line"><span>Model {retention.model_version}</span><span>Day-{retention.horizon_day} horizon</span><span>Band policy {retention.band_policy_version}</span></footer>
  </div>
}
