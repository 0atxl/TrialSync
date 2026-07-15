import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError, apiRequest, type ImportDocument, type PatientImportFact, type TrialImportCriterion } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ConfirmationDialog } from '../components/ConfirmationDialog'

export function ImportReviewPage() {
  const { importId = '' } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()
  const [review, setReview] = useState<ImportDocument | null>(null)
  const [ruleTexts, setRuleTexts] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [duplicateOpen, setDuplicateOpen] = useState(false)
  const [rejectOpen, setRejectOpen] = useState(false)

  const load = useCallback(async () => {
    try {
      const loaded = await apiRequest<ImportDocument>(`/imports/${importId}`, {}, token)
      setReview(loaded)
      setRuleTexts(Object.fromEntries((loaded.candidates.criteria ?? []).map((item) => [item.candidate_id, item.normalized_rule ? JSON.stringify(item.normalized_rule, null, 2) : ''])))
      setError('')
    } catch { setError('The import review could not be loaded.') }
  }, [importId, token])
  useEffect(() => { void load() }, [load])

  const back = review?.kind === 'trial' ? '/trials' : '/patients'
  const updateProfile = (key: string, value: string | null) => setReview((current) => current ? ({ ...current, candidates: { ...current.candidates, profile: { ...current.candidates.profile, [key]: value } } }) : current)
  const updateFact = (candidateId: string, values: Partial<PatientImportFact>) => setReview((current) => current ? ({ ...current, candidates: { ...current.candidates, facts: (current.candidates.facts ?? []).map((item) => item.candidate_id === candidateId ? { ...item, ...values } : item) } }) : current)
  const updateCriterion = (candidateId: string, values: Partial<TrialImportCriterion>) => setReview((current) => current ? ({ ...current, candidates: { ...current.candidates, criteria: (current.candidates.criteria ?? []).map((item) => item.candidate_id === candidateId ? { ...item, ...values } : item) } }) : current)

  const reviewedCandidates = () => {
    if (!review) return null
    const candidates = structuredClone(review.candidates)
    if (review.kind === 'trial') {
      for (const criterion of candidates.criteria ?? []) {
        const text = ruleTexts[criterion.candidate_id]?.trim()
        if (!text) { criterion.normalized_rule = null; criterion.parse_state = 'needs_manual_rule'; continue }
        const parsed = JSON.parse(text) as unknown
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Rule JSON must be an object.')
        criterion.normalized_rule = parsed as Record<string, unknown>
        criterion.parse_state = 'parsed'
      }
    }
    return candidates
  }

  const save = async () => {
    const candidates = reviewedCandidates()
    if (!candidates) throw new Error('Review is not loaded.')
    const saved = await apiRequest<ImportDocument>(`/imports/${importId}`, { method: 'PUT', body: JSON.stringify({ candidates }) }, token)
    setReview(saved)
    return saved
  }
  const saveReview = async () => {
    setSaving(true); setError('')
    try { await save() }
    catch (exception) { setError(exception instanceof SyntaxError || exception instanceof Error && exception.message.includes('Rule JSON') ? 'Each selected trial criterion needs valid rule JSON.' : 'The candidate edits could not be saved.') }
    finally { setSaving(false) }
  }
  const approve = async (confirmDuplicate = false) => {
    setSaving(true); setError('')
    try {
      const saved = await save()
      const approval = await apiRequest<{ resource_id: string }>(`/imports/${importId}/approve`, { method: 'POST', body: JSON.stringify({ confirm_duplicate_name: confirmDuplicate }) }, token)
      navigate(saved.kind === 'patient' ? `/patients/${approval.resource_id}` : `/trials/${approval.resource_id}`)
    } catch (exception) {
      if (exception instanceof ApiError && exception.code === 'PATIENT_NAME_REVIEW_REQUIRED') setDuplicateOpen(true)
      else if (exception instanceof ApiError && exception.code === 'IMPORT_REVIEW_INCOMPLETE') setError('Selected criteria need valid deterministic rule JSON before approval. Deselect unsupported criteria or enter a supported rule.')
      else if (exception instanceof SyntaxError) setError('Each selected trial criterion needs valid rule JSON.')
      else setError('The reviewed import could not be approved. No structured record was created.')
    } finally { setSaving(false) }
  }
  const reject = async () => {
    setSaving(true)
    try { await apiRequest(`/imports/${importId}`, { method: 'DELETE' }, token); navigate(back) }
    catch { setRejectOpen(false); setError('The import could not be rejected.') }
    finally { setSaving(false) }
  }

  if (error && !review) return <div className="form-error" role="alert">{error}</div>
  if (!review) return <div className="loading-state">Loading import review…</div>
  const profile = review.candidates.profile
  return <section className="route-entry workspace-page"><Link className="back-link" to={back}>← {review.kind === 'patient' ? 'Patients' : 'Trials'}</Link><header className="page-heading"><div><p className="eyebrow">Human review required</p><h1>Review extracted {review.kind} candidates</h1><p>Compare every editable candidate with its immutable source span before creating structured data.</p></div><span className="review-status">{review.status.replace('_', ' ')}</span></header>{review.warnings.length > 0 && <div className="import-warnings" role="status"><strong>Review warnings</strong><ul>{review.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div>}<div className="import-review-grid"><aside className="source-pane" aria-label="Imported source"><div className="source-pane-head"><div><p className="eyebrow">Original source</p><strong>{review.filename ?? 'Pasted text'}</strong></div><small>{review.quality.page_count} page{Number(review.quality.page_count) === 1 ? '' : 's'} · {review.quality.character_count} characters</small></div>{review.pages.map((page) => <section className="source-page" key={page.page}><span>Page {page.page}</span><pre>{page.text}</pre></section>)}</aside><div className="candidate-pane"><section className="candidate-section"><h2>{review.kind === 'patient' ? 'Patient profile' : 'Trial profile'}</h2><div className="form-grid">{review.kind === 'patient' ? <><label>Display name<input value={profile.display_name ?? ''} onChange={(event) => updateProfile('display_name', event.target.value)} /></label><label>Date of birth<input type="date" value={profile.date_of_birth ?? ''} onChange={(event) => updateProfile('date_of_birth', event.target.value || null)} /></label><label>Sex when relevant<input value={profile.sex ?? ''} onChange={(event) => updateProfile('sex', event.target.value || null)} /></label></> : <><label>Trial title<input value={profile.title ?? ''} onChange={(event) => updateProfile('title', event.target.value)} /></label><label>Condition<input value={profile.condition ?? ''} onChange={(event) => updateProfile('condition', event.target.value)} /></label><label>Phase<input value={profile.phase ?? ''} onChange={(event) => updateProfile('phase', event.target.value || null)} /></label></>}</div></section>{review.kind === 'patient' ? <PatientCandidates facts={review.candidates.facts ?? []} update={updateFact} /> : <TrialCandidates criteria={review.candidates.criteria ?? []} ruleTexts={ruleTexts} setRuleTexts={setRuleTexts} update={updateCriterion} />}{error && <div className="form-error" role="alert">{error}</div>}<div className="review-actions"><button className="danger-button danger-button-subtle" type="button" onClick={() => setRejectOpen(true)}>Reject import</button><div><button className="secondary-button" disabled={saving} type="button" onClick={() => void saveReview()}>{saving ? 'Saving…' : 'Save review'}</button><button className="primary-button" disabled={saving || review.status !== 'needs_review'} type="button" onClick={() => void approve()}>{saving ? 'Approving…' : `Approve and create ${review.kind}`}</button></div></div></div></div><ConfirmationDialog open={duplicateOpen} eyebrow="Possible duplicate" title="Create a distinct patient?" confirmLabel="Create distinct patient" busyLabel="Creating…" busy={saving} onCancel={() => setDuplicateOpen(false)} onConfirm={() => { setDuplicateOpen(false); void approve(true) }}><p>A patient with this name already exists. Continue only if this imported source represents a distinct synthetic person.</p></ConfirmationDialog><ConfirmationDialog open={rejectOpen} eyebrow="Discard candidates" title="Reject this import?" confirmLabel="Reject import" busyLabel="Rejecting…" busy={saving} onCancel={() => setRejectOpen(false)} onConfirm={() => void reject()}><p>The extracted candidates will be marked rejected and no patient or trial will be created.</p></ConfirmationDialog></section>
}

function PatientCandidates({ facts, update }: { facts: PatientImportFact[]; update: (id: string, values: Partial<PatientImportFact>) => void }) {
  return <section className="candidate-section"><div className="section-heading"><div><p className="eyebrow">Structured candidates</p><h2>Patient facts</h2></div><span>{facts.filter((item) => item.selected).length} selected</span></div>{facts.length ? facts.map((fact) => <article className="candidate-card" key={fact.candidate_id}><label className="candidate-select"><input type="checkbox" checked={fact.selected} onChange={(event) => update(fact.candidate_id, { selected: event.target.checked })} /> Include candidate</label><div className="candidate-fields"><label>Fact type<select value={fact.fact_type} onChange={(event) => update(fact.candidate_id, { fact_type: event.target.value as PatientImportFact['fact_type'] })}><option value="condition">Condition</option><option value="medication">Medication</option><option value="observation">Observation</option><option value="demographic">Demographic</option></select></label><label>Concept<input value={fact.concept} onChange={(event) => update(fact.candidate_id, { concept: event.target.value })} /></label><label>Numeric value<input inputMode="decimal" value={fact.value_numeric ?? ''} onChange={(event) => update(fact.candidate_id, { value_numeric: event.target.value || null })} /></label><label>Text value<input value={fact.value_text ?? ''} onChange={(event) => update(fact.candidate_id, { value_text: event.target.value || null })} /></label><label>Unit<input value={fact.unit ?? ''} onChange={(event) => update(fact.candidate_id, { unit: event.target.value || null })} /></label></div><SourceNote source={fact.source} />{fact.warnings.map((warning) => <p className="candidate-warning" key={warning}>{warning}</p>)}</article>) : <div className="empty-state"><h2>No recognized facts</h2><p>Create the patient profile, then add structured facts through manual entry.</p></div>}</section>
}

function TrialCandidates({ criteria, ruleTexts, setRuleTexts, update }: { criteria: TrialImportCriterion[]; ruleTexts: Record<string, string>; setRuleTexts: (values: Record<string, string>) => void; update: (id: string, values: Partial<TrialImportCriterion>) => void }) {
  return <section className="candidate-section"><div className="section-heading"><div><p className="eyebrow">Ordered candidates</p><h2>Trial criteria</h2></div><span>{criteria.filter((item) => item.selected).length} selected</span></div>{criteria.length ? criteria.map((criterion) => <article className="candidate-card" key={criterion.candidate_id}><div className="candidate-card-head"><label className="candidate-select"><input type="checkbox" checked={criterion.selected} onChange={(event) => update(criterion.candidate_id, { selected: event.target.checked })} /> Include criterion</label><span className={`parse-state parse-state-${criterion.parse_state}`}>{criterion.parse_state === 'parsed' ? 'Rule parsed' : 'Manual rule needed'}</span></div><div className="form-pair"><label>Kind<select value={criterion.kind} onChange={(event) => update(criterion.candidate_id, { kind: event.target.value as TrialImportCriterion['kind'] })}><option value="inclusion">Inclusion</option><option value="exclusion">Exclusion</option></select></label><label>Order<input min="1" type="number" value={criterion.order} onChange={(event) => update(criterion.candidate_id, { order: Number(event.target.value) })} /></label></div><label>Criterion source text<textarea rows={3} value={criterion.source_text} onChange={(event) => update(criterion.candidate_id, { source_text: event.target.value })} /></label><label>Deterministic rule JSON<textarea className="code-input" rows={5} value={ruleTexts[criterion.candidate_id] ?? ''} onChange={(event) => setRuleTexts({ ...ruleTexts, [criterion.candidate_id]: event.target.value })} placeholder='{"op":"present","fact":"condition.example"}' /></label><SourceNote source={criterion.source} />{criterion.warnings.map((warning) => <p className="candidate-warning" key={warning}>{warning}</p>)}</article>) : <div className="empty-state"><h2>No recognized criteria</h2><p>Return to manual trial entry or revise the source with explicit inclusion and exclusion lists.</p></div>}</section>
}

function SourceNote({ source }: { source: { page: number; text: string } }) {
  return <details className="source-note"><summary>Source · page {source.page}</summary><q>{source.text}</q></details>
}
