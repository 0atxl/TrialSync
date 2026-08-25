import { Search, Trash2 } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'

import {
  type Criterion,
  type PatientFactCatalogEntry,
  type PatientFactGroup,
  type TerminologySuggestion,
} from '../api/client'
import {
  suggestionCategory,
  suggestionSourceLabel,
  useTerminologySuggestions,
} from '../hooks/useTerminologySuggestions'
import type {
  GuidedCriterionSubmission,
  UnsupportedCriterionSubmission,
} from './TrialCriterionEditor'
import { TerminologySetupDialog } from './TerminologySetupDialog'

export type CriterionDraft = GuidedCriterionSubmission & {
  id: string
  label: string
}

export type UnsupportedCriterionDraft = UnsupportedCriterionSubmission & {
  id: string
}

type Subject = {
  key: string
  label: string
  group: PatientFactGroup | 'demographics'
  numeric: boolean
  unit: string | null
}

const groupLabels: Record<PatientFactGroup | 'demographics' | 'all', string> = {
  all: 'All',
  demographics: 'Demographics',
  conditions: 'Conditions',
  medications: 'Medications',
  observations: 'Labs and observations',
}

let criterionSequence = 0
function criterionId(prefix: string) {
  criterionSequence += 1
  return `${prefix}-${criterionSequence}`
}

function summary(criterion: CriterionDraft) {
  if (criterion.subject_key === 'biological_sex') {
    return criterion.biological_sex === 'female' ? 'Female' : 'Male'
  }
  if (criterion.operator === 'present') return 'Present'
  if (criterion.operator === 'absent') return 'Absent'
  if (criterion.operator === 'between') return `${criterion.minimum} to ${criterion.maximum}`
  return `${criterion.operator === 'gte' ? 'At least' : 'At most'} ${criterion.value}`
}

export function CriterionComposer({
  kind,
  entries,
  token,
  canCreateSupportedTerm,
  criteria,
  unsupported,
  onCriteriaChange,
  onUnsupportedChange,
  onCatalogEntryCreated,
}: {
  kind: Criterion['kind']
  entries: PatientFactCatalogEntry[]
  token: string | null
  canCreateSupportedTerm: boolean
  criteria: CriterionDraft[]
  unsupported: UnsupportedCriterionDraft[]
  onCriteriaChange: (criteria: CriterionDraft[]) => void
  onUnsupportedChange: (criteria: UnsupportedCriterionDraft[]) => void
  onCatalogEntryCreated: (entry: PatientFactCatalogEntry) => void
}) {
  const [query, setQuery] = useState('')
  const [group, setGroup] = useState<PatientFactGroup | 'demographics' | 'all'>('all')
  const [selected, setSelected] = useState<Subject | null>(null)
  const [operator, setOperator] = useState<GuidedCriterionSubmission['operator']>('present')
  const [value, setValue] = useState('')
  const [minimum, setMinimum] = useState('')
  const [maximum, setMaximum] = useState('')
  const [biologicalSex, setBiologicalSex] = useState<'female' | 'male'>('female')
  const [fieldError, setFieldError] = useState('')
  const [setupSuggestion, setSetupSuggestion] = useState<TerminologySuggestion | null>(null)
  const { suggestions, suggesting, suggestionNotice } =
    useTerminologySuggestions(query, group, token)

  const subjects = useMemo<Subject[]>(() => [
    { key: 'age', label: 'Age', group: 'demographics', numeric: true, unit: 'years' },
    { key: 'biological_sex', label: 'Biological sex', group: 'demographics', numeric: false, unit: null },
    ...entries.filter((entry) => entry.screening_supported).map((entry) => ({
      key: entry.key,
      label: entry.display_label,
      group: entry.group,
      numeric: entry.input_kind === 'numeric',
      unit: entry.fixed_unit,
    })),
  ], [entries])

  const available = useMemo(() => {
    const term = query.trim().toLowerCase()
    return subjects.filter((subject) =>
      (group === 'all' || subject.group === group) &&
      (!term || subject.label.toLowerCase().includes(term)),
    ).slice(0, 10)
  }, [group, query, subjects])

  const chooseSubject = (subject: Subject) => {
    setSelected(subject)
    setOperator(subject.key === 'biological_sex' ? 'is' : subject.numeric ? 'between' : 'present')
    setValue('')
    setMinimum(subject.key === 'age' ? '18' : '')
    setMaximum(subject.key === 'age' ? '75' : '')
    setFieldError('')
  }

  const addCriterion = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selected) return
    const numericValue = value === '' ? null : Number(value)
    const numericMinimum = minimum === '' ? null : Number(minimum)
    const numericMaximum = maximum === '' ? null : Number(maximum)
    if (selected.numeric && operator === 'between' && (numericMinimum === null || numericMaximum === null || numericMinimum > numericMaximum)) {
      setFieldError('Enter a valid minimum and maximum.')
      return
    }
    if (selected.numeric && operator !== 'between' && numericValue === null) {
      setFieldError('Enter a threshold.')
      return
    }
    onCriteriaChange([...criteria, {
      id: criterionId('criterion'),
      label: selected.label,
      kind,
      subject_key: selected.key,
      operator,
      value: numericValue,
      minimum: numericMinimum,
      maximum: numericMaximum,
      biological_sex: selected.key === 'biological_sex' ? biologicalSex : null,
    }])
    setSelected(null)
    setQuery('')
  }

  const selectSuggestion = (suggestion: TerminologySuggestion) => {
    const supported = subjects.find(
      (subject) => subject.label.trim().toLowerCase() === suggestion.display_label.trim().toLowerCase(),
    )
    if (supported) {
      chooseSubject(supported)
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
      id: criterionId('review'),
      kind,
      category,
      source_text: suggestion.display_label,
    }])
    setSetupSuggestion(null)
    setQuery('')
  }

  const useSupportedTerm = (entry: PatientFactCatalogEntry) => {
    onCatalogEntryCreated(entry)
    chooseSubject({
      key: entry.key,
      label: entry.display_label,
      group: entry.group,
      numeric: entry.input_kind === 'numeric',
      unit: entry.fixed_unit,
    })
    setSetupSuggestion(null)
    setQuery('')
  }

  return (
    <div className="criterion-composer">
      {(criteria.length > 0 || unsupported.length > 0) ? <div className="draft-criterion-list">
        {criteria.map((criterion) => <div key={criterion.id}><span><strong>{criterion.label}</strong><small>{summary(criterion)}</small></span><button aria-label={`Remove ${criterion.label}`} type="button" onClick={() => onCriteriaChange(criteria.filter((item) => item.id !== criterion.id))}><Trash2 aria-hidden="true" size={17} /></button></div>)}
        {unsupported.map((criterion) => <div className="review-only" key={criterion.id}><span><strong>{criterion.source_text}</strong><small>Choose a supported criterion before saving</small></span><button aria-label={`Remove ${criterion.source_text}`} type="button" onClick={() => onUnsupportedChange(unsupported.filter((item) => item.id !== criterion.id))}><Trash2 aria-hidden="true" size={17} /></button></div>)}
      </div> : null}
      {!selected ? <section className="catalog-inline-search" aria-labelledby={`${kind}-criterion-search-title`}>
        <div className="inline-search-heading"><div><h3 id={`${kind}-criterion-search-title`}>Add {kind} criterion</h3></div></div>
        <label className="catalog-search-input"><Search aria-hidden="true" size={17} /><span className="sr-only">Search supported criteria</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Age, condition, medication, or lab" /></label>
        <div className="catalog-groups compact" aria-label="Criterion categories">{(Object.keys(groupLabels) as Array<PatientFactGroup | 'demographics' | 'all'>).map((key) => <button aria-pressed={group === key} className={group === key ? 'selected' : ''} key={key} type="button" onClick={() => setGroup(key)}>{groupLabels[key]}</button>)}</div>
        {query.trim() || group !== 'all' ? <div className="inline-catalog-results">{available.map((subject) => <button key={subject.key} type="button" onClick={() => chooseSubject(subject)}><span><strong>{subject.label}</strong><small>{groupLabels[subject.group]}</small></span>{subject.unit ? <b>{subject.unit}</b> : null}</button>)}{suggestions.map((suggestion) => <button className="external-suggestion" key={`${suggestion.source}-${suggestion.code}`} type="button" onClick={() => selectSuggestion(suggestion)}><span><strong>{suggestion.display_label}</strong><small>{suggestionSourceLabel(suggestion)} · set up</small></span></button>)}{!available.length && !suggestions.length && !suggesting ? <p>No matching criteria.</p> : null}{suggesting ? <p>Checking live suggestions…</p> : null}{suggestionNotice ? <p className="suggestion-notice">{suggestionNotice}</p> : null}</div> : null}
      </section> : <form className="inline-detail-editor criterion-inline-editor" onSubmit={addCriterion}>
        <div className="inline-editor-head"><div><small>{kind} criterion</small><h3>{selected.label}</h3></div><button className="text-button" type="button" onClick={() => setSelected(null)}>Choose another</button></div>
        {selected.key === 'biological_sex' ? <fieldset className="detail-status-field"><legend>Required biological sex</legend><div>{(['female', 'male'] as const).map((sex) => <label key={sex}><input checked={biologicalSex === sex} name={`${kind}-criterion-sex`} type="radio" onChange={() => setBiologicalSex(sex)} /><span>{sex === 'female' ? 'Female' : 'Male'}</span></label>)}</div></fieldset> : selected.numeric ? <><fieldset className="detail-status-field"><legend>Comparison</legend><div>{([['gte', 'At least'], ['lte', 'At most'], ['between', 'Between']] as const).map(([nextOperator, label]) => <label key={nextOperator}><input checked={operator === nextOperator} name={`${kind}-criterion-operator`} type="radio" onChange={() => setOperator(nextOperator)} /><span>{label}</span></label>)}</div></fieldset>{operator === 'between' ? <div className="form-pair"><label>Minimum<input aria-label="Minimum" type="number" step="any" value={minimum} onChange={(event) => setMinimum(event.target.value)} /></label><label>Maximum<input aria-label="Maximum" type="number" step="any" value={maximum} onChange={(event) => setMaximum(event.target.value)} /></label></div> : <label>Threshold<input aria-label="Threshold" type="number" step="any" value={value} onChange={(event) => setValue(event.target.value)} /></label>}</> : <fieldset className="detail-status-field"><legend>Required state</legend><div>{([['present', 'Present'], ['absent', 'Absent']] as const).map(([nextOperator, label]) => <label key={nextOperator}><input checked={operator === nextOperator} name={`${kind}-criterion-state`} type="radio" onChange={() => setOperator(nextOperator)} /><span>{label}</span></label>)}</div></fieldset>}
        {fieldError ? <div className="field-error" role="alert">{fieldError}</div> : null}
        <button className="secondary-button" type="submit">Add criterion</button>
      </form>}
      <TerminologySetupDialog
        suggestion={setupSuggestion}
        token={token}
        canCreateSupportedTerm={canCreateSupportedTerm}
        reviewLabel="Keep for review"
        onCancel={() => setSetupSuggestion(null)}
        onKeepForReview={keepForReview}
        onSupported={useSupportedTerm}
      />
    </div>
  )
}
