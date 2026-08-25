import { Search, Trash2 } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'

import {
  type BiologicalSex,
  type ClinicalDetailValue,
  type Fact,
  type PatientFactCatalogEntry,
  type PatientFactGroup,
  type PatientUnsupportedDetailCategory,
  type TerminologySuggestion,
} from '../api/client'
import {
  suggestionCategory,
  suggestionSourceLabel,
  useTerminologySuggestions,
} from '../hooks/useTerminologySuggestions'
import { todayIsoDate } from '../utils/dates'
import { TerminologySetupDialog } from './TerminologySetupDialog'

export type ClinicalDetailDraft = {
  id: string
  catalogKey: string
  label: string
  group: PatientFactGroup
  unit: string | null
  value: ClinicalDetailValue
}

export type UnsupportedClinicalDraft = {
  id: string
  category: PatientUnsupportedDetailCategory
  label: string
  context: string | null
}

const groupLabels: Record<PatientFactGroup | 'all', string> = {
  all: 'All',
  conditions: 'Conditions',
  medications: 'Medications',
  observations: 'Labs and observations',
}

let draftSequence = 0
function draftId(prefix: string) {
  draftSequence += 1
  return `${prefix}-${draftSequence}`
}

function valueSummary(detail: ClinicalDetailDraft) {
  if (detail.value.assertion === 'unknown') return 'Unknown'
  if (detail.value.input_kind === 'numeric') {
    return `${detail.value.value_numeric ?? 'No result'}${detail.unit ? ` ${detail.unit}` : ''}`
  }
  if (detail.value.input_kind === 'pregnancy_status') {
    return detail.value.assertion === 'present' ? 'Pregnant' : 'Not pregnant'
  }
  return detail.value.assertion === 'present' ? 'Present' : 'Absent'
}

export function ClinicalDetailComposer({
  entries,
  token,
  canCreateSupportedTerm,
  biologicalSex,
  details,
  unsupported,
  onDetailsChange,
  onUnsupportedChange,
  onCatalogEntryCreated,
}: {
  entries: PatientFactCatalogEntry[]
  token: string | null
  canCreateSupportedTerm: boolean
  biologicalSex: BiologicalSex | null
  details: ClinicalDetailDraft[]
  unsupported: UnsupportedClinicalDraft[]
  onDetailsChange: (details: ClinicalDetailDraft[]) => void
  onUnsupportedChange: (details: UnsupportedClinicalDraft[]) => void
  onCatalogEntryCreated: (entry: PatientFactCatalogEntry) => void
}) {
  const [query, setQuery] = useState('')
  const [group, setGroup] = useState<PatientFactGroup | 'all'>('all')
  const [selected, setSelected] = useState<PatientFactCatalogEntry | null>(null)
  const [assertion, setAssertion] = useState<Fact['assertion']>('present')
  const [numericValue, setNumericValue] = useState('')
  const [effectiveDate, setEffectiveDate] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [setupSuggestion, setSetupSuggestion] = useState<TerminologySuggestion | null>(null)
  const { suggestions, suggesting, suggestionNotice } =
    useTerminologySuggestions(query, group, token)

  const available = useMemo(() => {
    const term = query.trim().toLowerCase()
    const selectedKeys = new Set(details.map((detail) => detail.catalogKey))
    return entries.filter((entry) =>
      !selectedKeys.has(entry.key) &&
      (group === 'all' || entry.group === group) &&
      (!term || `${entry.display_label} ${entry.help_text}`.toLowerCase().includes(term)),
    ).slice(0, 10)
  }, [details, entries, group, query])

  const selectEntry = (entry: PatientFactCatalogEntry) => {
    setSelected(entry)
    setAssertion(entry.input_kind === 'pregnancy_status' && biologicalSex === 'male' ? 'unknown' : 'present')
    setNumericValue('')
    setEffectiveDate(entry.effective_date_required ? todayIsoDate() : '')
    setFieldError('')
  }

  const addDetail = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selected) return
    if (selected.effective_date_required && !effectiveDate) {
      setFieldError('Enter the assessment or result date.')
      return
    }
    let value: ClinicalDetailValue
    if (selected.input_kind === 'numeric') {
      const numeric = numericValue.trim() === '' ? null : Number(numericValue)
      if (assertion === 'present' && (numeric === null || Number.isNaN(numeric))) {
        setFieldError('Enter a numeric result or choose Unknown.')
        return
      }
      value = {
        input_kind: 'numeric',
        assertion: assertion === 'unknown' ? 'unknown' : 'present',
        value_numeric: assertion === 'unknown' ? null : numeric,
        effective_date: effectiveDate,
      }
    } else if (selected.input_kind === 'pregnancy_status') {
      value = { input_kind: 'pregnancy_status', assertion, effective_date: effectiveDate }
    } else {
      value = { input_kind: 'status', assertion, effective_date: effectiveDate || null }
    }
    onDetailsChange([...details, {
      id: draftId('detail'),
      catalogKey: selected.key,
      label: selected.display_label,
      group: selected.group,
      unit: selected.fixed_unit,
      value,
    }])
    setSelected(null)
    setQuery('')
    setFieldError('')
  }

  const selectSuggestion = (suggestion: TerminologySuggestion) => {
    const supported = entries.find(
      (entry) => entry.display_label.trim().toLowerCase() === suggestion.display_label.trim().toLowerCase(),
    )
    if (supported) {
      selectEntry(supported)
      setQuery('')
      return
    }
    setSetupSuggestion(suggestion)
  }

  const keepForReview = (
    suggestion: TerminologySuggestion,
    category = suggestionCategory(suggestion),
  ) => {
    onUnsupportedChange([...unsupported, {
      id: draftId('review'),
      category,
      label: suggestion.display_label,
      context: null,
    }])
    setSetupSuggestion(null)
    setQuery('')
  }

  const useSupportedTerm = (entry: PatientFactCatalogEntry) => {
    onCatalogEntryCreated(entry)
    selectEntry(entry)
    setSetupSuggestion(null)
    setQuery('')
  }

  return (
    <div className="clinical-composer">
      {(details.length > 0 || unsupported.length > 0) ? (
        <div className="draft-detail-list" aria-label="Clinical details to save">
          {details.map((detail) => (
            <div key={detail.id}>
              <span><strong>{detail.label}</strong><small>{valueSummary(detail)}{detail.value.effective_date ? ` · ${detail.value.effective_date}` : ''}</small></span>
              <button aria-label={`Remove ${detail.label}`} type="button" onClick={() => onDetailsChange(details.filter((item) => item.id !== detail.id))}><Trash2 aria-hidden="true" size={17} /></button>
            </div>
          ))}
          {unsupported.map((detail) => (
            <div className="review-only" key={detail.id}>
              <span><strong>{detail.label}</strong><small>Review item · not used for screening</small></span>
              <button aria-label={`Remove ${detail.label}`} type="button" onClick={() => onUnsupportedChange(unsupported.filter((item) => item.id !== detail.id))}><Trash2 aria-hidden="true" size={17} /></button>
            </div>
          ))}
        </div>
      ) : null}

      {!selected ? (
        <section className="catalog-inline-search" aria-labelledby="clinical-search-title">
          <div className="inline-search-heading"><div><h3 id="clinical-search-title">Add clinical details</h3></div></div>
          <label className="catalog-search-input">
            <Search aria-hidden="true" size={17} />
            <span className="sr-only">Search clinical details</span>
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Condition, medication, or lab" />
          </label>
          <div className="catalog-groups compact" aria-label="Clinical detail categories">
            {(Object.keys(groupLabels) as Array<PatientFactGroup | 'all'>).map((key) => (
              <button aria-pressed={group === key} className={group === key ? 'selected' : ''} key={key} type="button" onClick={() => setGroup(key)}>{groupLabels[key]}</button>
            ))}
          </div>
          {query.trim() || group !== 'all' ? (
            <div className="inline-catalog-results">
              {available.map((entry) => <button key={entry.key} type="button" onClick={() => selectEntry(entry)}><span><strong>{entry.display_label}</strong><small>{groupLabels[entry.group]}</small></span>{entry.fixed_unit ? <b>{entry.fixed_unit}</b> : null}</button>)}
              {suggestions.map((suggestion) => <button className="external-suggestion" key={`${suggestion.source}-${suggestion.code}`} type="button" onClick={() => selectSuggestion(suggestion)}><span><strong>{suggestion.display_label}</strong><small>{suggestionSourceLabel(suggestion)} · set up</small></span></button>)}
              {!available.length && !suggestions.length && !suggesting ? <p>No matching clinical details.</p> : null}
              {suggesting ? <p>Checking more suggestions…</p> : null}
              {suggestionNotice ? <p className="suggestion-notice" role="status">{suggestionNotice}</p> : null}
            </div>
          ) : null}
        </section>
      ) : (
        <form className="inline-detail-editor" noValidate onSubmit={addDetail}>
          <div className="inline-editor-head"><div><small>{groupLabels[selected.group]}</small><h3>{selected.display_label}</h3></div><button className="text-button" type="button" onClick={() => setSelected(null)}>Choose another</button></div>
          <fieldset className="detail-status-field"><legend>{selected.input_kind === 'numeric' ? 'Result status' : 'Status'}</legend><div>{selected.allowed_assertions.map((value) => <label key={value}><input checked={assertion === value} disabled={selected.input_kind === 'pregnancy_status' && biologicalSex === 'male' && value === 'present'} name="new-detail-status" type="radio" onChange={() => setAssertion(value)} /><span>{selected.input_kind === 'pregnancy_status' ? value === 'present' ? 'Pregnant' : value === 'absent' ? 'Not pregnant' : 'Unknown' : value === 'present' ? 'Present' : value === 'absent' ? 'Absent' : 'Unknown'}</span></label>)}</div></fieldset>
          {selected.input_kind === 'numeric' && assertion !== 'unknown' ? <label className="numeric-detail-input">Result<span><input aria-label="Result" inputMode="decimal" type="number" step="any" value={numericValue} onChange={(event) => setNumericValue(event.target.value)} /><strong>{selected.fixed_unit}</strong></span></label> : null}
          <label>{selected.input_kind === 'numeric' ? 'Result date' : 'Assessed date'}<input max={todayIsoDate()} required={selected.effective_date_required} type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} />{!selected.effective_date_required ? <small>Optional</small> : null}</label>
          {fieldError ? <div className="field-error" role="alert">{fieldError}</div> : null}
          <button className="secondary-button" type="submit">Add detail</button>
        </form>
      )}
      <TerminologySetupDialog
        suggestion={setupSuggestion}
        token={token}
        canCreateSupportedTerm={canCreateSupportedTerm}
        reviewLabel="Keep in patient record"
        onCancel={() => setSetupSuggestion(null)}
        onKeepForReview={keepForReview}
        onSupported={useSupportedTerm}
      />
    </div>
  )
}
