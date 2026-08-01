import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import {
  ApiError,
  apiRequest,
  type ClinicalConcept,
  type TerminologySuggestion,
  type TerminologySuggestionResponse,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { useToast } from '../components/ToastProvider'

type NewConcept = {
  display_label: string
  fact_type: ClinicalConcept['fact_type']
  fixed_unit: string
  screening_supported: boolean
  help_text: string
  terminology_system: TerminologySuggestion['source'] | null
  terminology_code: string | null
}

const emptyConcept: NewConcept = {
  display_label: '',
  fact_type: 'condition',
  fixed_unit: '',
  screening_supported: true,
  help_text: '',
  terminology_system: null,
  terminology_code: null,
}

export function CatalogManagementPage() {
  const { token, user } = useAuth()
  const { showToast } = useToast()
  const [concepts, setConcepts] = useState<ClinicalConcept[]>([])
  const [query, setQuery] = useState('')
  const [showRetired, setShowRetired] = useState(false)
  const [draft, setDraft] = useState<NewConcept>(emptyConcept)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [changingId, setChangingId] = useState('')
  const [suggestions, setSuggestions] = useState<TerminologySuggestion[]>([])
  const [suggestionNotice, setSuggestionNotice] = useState('')
  const [suggesting, setSuggesting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setConcepts(await apiRequest<ClinicalConcept[]>('/clinical-concepts', {}, token))
      setError('')
    } catch (exception) {
      setError(
        exception instanceof ApiError && exception.status === 403
          ? 'This account is not allowed to manage the shared clinical catalog.'
          : 'The clinical catalog could not be loaded.',
      )
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    return concepts.filter((concept) =>
      (showRetired || concept.active) &&
      (!term || `${concept.display_label} ${concept.key} ${concept.help_text}`.toLowerCase().includes(term)),
    )
  }, [concepts, query, showRetired])

  const createConcept = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    try {
      const created = await apiRequest<ClinicalConcept>('/clinical-concepts', {
        method: 'POST',
        body: JSON.stringify({
          display_label: draft.display_label,
          fact_type: draft.fact_type,
          fixed_unit: draft.fact_type === 'observation' ? draft.fixed_unit || null : null,
          screening_supported: draft.screening_supported,
          help_text: draft.help_text || null,
          terminology_system: draft.terminology_system,
          terminology_code: draft.terminology_code,
        }),
      }, token)
      setConcepts((current) => [...current, created])
      setDraft(emptyConcept)
      setError('')
      showToast({
        variant: 'success',
        title: 'Clinical detail added',
        message: `${created.display_label} is now available in patient entry${created.screening_supported ? ' and trial criteria' : ''}.`,
      })
    } catch (exception) {
      const message = exception instanceof ApiError ? exception.message : 'The clinical detail could not be added.'
      setError(message)
      showToast({ variant: 'error', title: 'Clinical detail not added', message, announce: false })
    } finally {
      setSaving(false)
    }
  }

  const findSuggestions = async () => {
    if (draft.fact_type === 'condition') {
      setSuggestions([])
      setSuggestionNotice('External suggestions currently cover medications and observations.')
      return
    }
    const query = draft.display_label.trim()
    if (query.length < 2) {
      setSuggestionNotice('Enter at least two characters in Display name before searching.')
      return
    }
    setSuggesting(true)
    setSuggestionNotice('')
    try {
      const response = await apiRequest<TerminologySuggestionResponse>(
        `/clinical-concepts/suggestions?query=${encodeURIComponent(query)}&fact_type=${draft.fact_type}`,
        {},
        token,
      )
      setSuggestions(response.suggestions)
      setSuggestionNotice(response.unavailable_sources.join(' '))
    } catch {
      setSuggestions([])
      setSuggestionNotice('Suggestions could not be loaded. You can still add a local detail manually.')
    } finally {
      setSuggesting(false)
    }
  }

  const selectSuggestion = (suggestion: TerminologySuggestion) => {
    setDraft({
      ...draft,
      display_label: suggestion.display_label,
      fixed_unit: draft.fact_type === 'observation' ? suggestion.fixed_unit ?? draft.fixed_unit : '',
      terminology_system: suggestion.source,
      terminology_code: suggestion.code,
    })
    setSuggestions([])
    setSuggestionNotice(`${suggestion.source === 'rxnorm' ? 'RxNorm' : 'LOINC'} code ${suggestion.code} selected. Review the fields, then add the local detail.`)
  }

  const changeConcept = async (concept: ClinicalConcept, action: 'retire' | 'restore' | 'screening') => {
    if (changingId) return
    setChangingId(concept.id)
    try {
      const updated = action === 'screening'
        ? await apiRequest<ClinicalConcept>(`/clinical-concepts/${concept.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ screening_supported: !concept.screening_supported }),
        }, token)
        : await apiRequest<ClinicalConcept>(`/clinical-concepts/${concept.id}/${action}`, { method: 'POST' }, token)
      setConcepts((current) => current.map((item) => item.id === updated.id ? updated : item))
      showToast({
        variant: 'success',
        title: action === 'retire' ? 'Clinical detail retired' : action === 'restore' ? 'Clinical detail restored' : 'Trial availability updated',
        message: action === 'retire'
          ? `${concept.display_label} is no longer offered for new entries.`
          : action === 'restore'
            ? `${concept.display_label} is available for new entries again.`
            : `${concept.display_label} is ${updated.screening_supported ? 'available' : 'not available'} for trial criteria.`,
      })
    } catch {
      const message = 'The clinical catalog could not be updated. No changes were made.'
      setError(message)
      showToast({ variant: 'error', title: 'Catalog update failed', message, announce: false })
    } finally {
      setChangingId('')
    }
  }

  if (!user?.is_catalog_admin) {
    return <section className="route-entry workspace-page narrow-page"><header className="page-heading"><p className="eyebrow">Catalog access</p><h1>Clinical catalog</h1></header><div className="form-error" role="alert">This account is not allowed to manage the shared clinical catalog.</div><Link className="secondary-button" to="/patients">Back to patients</Link></section>
  }

  return <section className="route-entry workspace-page catalog-page">
    <header className="page-heading"><div><p className="eyebrow">Shared definitions</p><h1>Clinical catalog</h1><p>Manage the local concepts available in patient records and trial criteria. Retiring a concept never changes saved records or screenings.</p></div></header>
    <div className="catalog-management-grid">
      <form className="catalog-create-panel" onSubmit={createConcept}>
        <div><p className="eyebrow">Add local detail</p><h2>New clinical concept</h2><p>Use a clear label. TrialSync creates the internal key and safe input controls.</p></div>
        <label>Display name<input autoFocus value={draft.display_label} onChange={(event) => setDraft({ ...draft, display_label: event.target.value, terminology_system: null, terminology_code: null })} placeholder="e.g. C-reactive protein" required /></label>
        <label>Category<select value={draft.fact_type} onChange={(event) => { setDraft({ ...draft, fact_type: event.target.value as NewConcept['fact_type'], fixed_unit: '', terminology_system: null, terminology_code: null }); setSuggestions([]); setSuggestionNotice('') }}><option value="condition">Condition</option><option value="medication">Medication</option><option value="observation">Lab or observation</option></select></label>
        <div className="terminology-lookup"><button className="secondary-button" disabled={suggesting} type="button" onClick={() => void findSuggestions()}>{suggesting ? 'Searching…' : draft.fact_type === 'medication' ? 'Find RxNorm suggestion' : draft.fact_type === 'observation' ? 'Find LOINC suggestion' : 'External lookup unavailable'}</button><small>Suggestions never create a detail automatically. Select one only after reviewing it.</small>{suggestionNotice ? <p role="status">{suggestionNotice}</p> : null}{suggestions.length ? <div className="terminology-suggestions">{suggestions.map((suggestion) => <button key={`${suggestion.source}-${suggestion.code}`} type="button" onClick={() => selectSuggestion(suggestion)}><strong>{suggestion.display_label}</strong><span>{suggestion.source === 'rxnorm' ? 'RxNorm' : 'LOINC'} · {suggestion.code}{suggestion.fixed_unit ? ` · ${suggestion.fixed_unit}` : ''}</span>{suggestion.detail ? <small>{suggestion.detail}</small> : null}</button>)}</div> : null}</div>
        {draft.fact_type === 'observation' ? <label>Fixed unit<input value={draft.fixed_unit} onChange={(event) => setDraft({ ...draft, fixed_unit: event.target.value })} placeholder="e.g. mg/L" required /></label> : null}
        <label>Guidance for entry<textarea value={draft.help_text} onChange={(event) => setDraft({ ...draft, help_text: event.target.value })} placeholder="Optional guidance shown while entering this detail." rows={3} /></label>
        <label className="catalog-checkbox"><input type="checkbox" checked={draft.screening_supported} onChange={(event) => setDraft({ ...draft, screening_supported: event.target.checked })} /><span><strong>Available in trial criteria</strong><small>Turn this off for details that should be recorded but not screened.</small></span></label>
        <button className="primary-button" disabled={saving} type="submit">{saving ? 'Adding…' : 'Add clinical detail'}</button>
      </form>

      <section className="catalog-list-panel" aria-labelledby="catalog-list-heading">
        <div className="catalog-list-heading"><div><p className="eyebrow">Searchable catalog</p><h2 id="catalog-list-heading">{concepts.filter((item) => item.active).length} active details</h2></div><label className="catalog-retired-toggle"><input type="checkbox" checked={showRetired} onChange={(event) => setShowRetired(event.target.checked)} /> Show retired</label></div>
        <label className="search-field"><span>Search clinical details</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, key, or guidance" /></label>
        {error ? <div className="form-error" role="alert"><span>{error}</span><button className="text-button" type="button" onClick={() => void load()}>Try again</button></div> : null}
        {loading ? <div className="loading-state">Loading shared clinical details…</div> : visible.length === 0 ? <div className="empty-state"><h3>No matching details</h3><p>Try another search or add a local clinical concept.</p></div> : <div className="catalog-concept-list">{visible.map((concept) => <article className={`catalog-concept-row${concept.active ? '' : ' retired'}`} key={concept.id}><div><strong>{concept.display_label}</strong><small>{concept.fact_type} · {concept.input_kind === 'numeric' ? concept.fixed_unit : 'present / absent / unknown'} · {concept.screening_supported ? 'trial criteria enabled' : 'record entry only'}</small><span>{concept.help_text}</span></div><div className="record-actions">{concept.active ? <><button className="text-button" disabled={changingId === concept.id} type="button" onClick={() => void changeConcept(concept, 'screening')}>{concept.screening_supported ? 'Remove from trials' : 'Use in trials'}</button><button className="text-button danger" disabled={changingId === concept.id} type="button" onClick={() => void changeConcept(concept, 'retire')}>Retire</button></> : <button className="text-button" disabled={changingId === concept.id} type="button" onClick={() => void changeConcept(concept, 'restore')}>Restore</button>}</div></article>)}</div>}
      </section>
    </div>
  </section>
}
