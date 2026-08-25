import { useEffect, useRef, useState } from 'react'

import {
  ApiError,
  apiRequest,
  type ClinicalConcept,
  type PatientFactCatalogEntry,
  type TerminologySuggestion,
} from '../api/client'
import { suggestionCategory, suggestionSourceLabel } from '../hooks/useTerminologySuggestions'

type SetupCategory = 'condition' | 'medication' | 'observation'

type TerminologySetupDialogProps = {
  suggestion: TerminologySuggestion | null
  token: string | null
  canCreateSupportedTerm: boolean
  reviewLabel: string
  onCancel: () => void
  onKeepForReview: (suggestion: TerminologySuggestion, category: SetupCategory) => void
  onSupported: (entry: PatientFactCatalogEntry) => void
}

const categoryLabels: Record<SetupCategory, string> = {
  condition: 'Condition',
  medication: 'Medication',
  observation: 'Lab or observation',
}

function initialCategory(suggestion: TerminologySuggestion): SetupCategory {
  const category = suggestionCategory(suggestion)
  return category === 'other' ? 'condition' : category
}

function catalogEntryFromConcept(concept: ClinicalConcept): PatientFactCatalogEntry {
  return {
    key: concept.key,
    fact_type: concept.fact_type,
    concept: concept.concept,
    display_label: concept.display_label,
    group: concept.concept_group,
    input_kind: concept.input_kind,
    allowed_assertions: concept.allowed_assertions_json,
    fixed_unit: concept.fixed_unit,
    allowed_units: concept.fixed_unit ? [concept.fixed_unit] : [],
    effective_date_required: concept.effective_date_required,
    screening_supported: concept.screening_supported,
    help_text: concept.help_text,
    terminology_system: concept.terminology_system,
    terminology_code: concept.terminology_code,
    display_order: concept.display_order,
  }
}

function terminologyProvenance(
  suggestion: TerminologySuggestion,
  category: SetupCategory,
) {
  if (suggestion.source === 'rxnorm' && category === 'medication') {
    return { terminology_system: 'rxnorm', terminology_code: suggestion.code }
  }
  if (suggestion.source === 'loinc' && category === 'observation') {
    return { terminology_system: 'loinc', terminology_code: suggestion.code }
  }
  return { terminology_system: null, terminology_code: null }
}

export function TerminologySetupDialog({
  suggestion,
  token,
  canCreateSupportedTerm,
  reviewLabel,
  onCancel,
  onKeepForReview,
  onSupported,
}: TerminologySetupDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [category, setCategory] = useState<SetupCategory>('condition')
  const [unit, setUnit] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (suggestion && !dialog.open) {
      setCategory(initialCategory(suggestion))
      setUnit(suggestion.fixed_unit ?? '')
      setError('')
      setSaving(false)
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
    }
    if (!suggestion && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [suggestion])

  if (!suggestion) {
    return <dialog ref={dialogRef} className="terminology-setup-dialog" />
  }

  const createSupportedTerm = async () => {
    const normalizedUnit = unit.trim()
    if (category === 'observation' && !normalizedUnit) {
      setError('Enter the unit used for this result.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const provenance = terminologyProvenance(suggestion, category)
      const created = await apiRequest<ClinicalConcept>('/clinical-concepts', {
        method: 'POST',
        body: JSON.stringify({
          display_label: suggestion.display_label,
          fact_type: category,
          fixed_unit: category === 'observation' ? normalizedUnit : null,
          screening_supported: true,
          ...provenance,
        }),
      }, token)
      onSupported(catalogEntryFromConcept(created))
    } catch (exception) {
      setError(exception instanceof ApiError
        ? exception.message
        : 'This term could not be added. Your selection is still here.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className="terminology-setup-dialog"
      aria-labelledby="terminology-setup-title"
      onCancel={(event) => {
        event.preventDefault()
        if (!saving) onCancel()
      }}
    >
      <form method="dialog" onSubmit={(event) => event.preventDefault()}>
        <header>
          <div>
            <small>{suggestionSourceLabel(suggestion)} suggestion</small>
            <h2 id="terminology-setup-title">Set up {suggestion.display_label}</h2>
          </div>
          <button aria-label="Close term setup" className="dialog-close" disabled={saving} type="button" onClick={onCancel}>×</button>
        </header>

        <div className="terminology-setup-fields">
          <label>
            Category
            <select autoFocus value={category} onChange={(event) => {
              setCategory(event.target.value as SetupCategory)
              setError('')
            }}>
              {(Object.keys(categoryLabels) as SetupCategory[]).map((value) => (
                <option key={value} value={value}>{categoryLabels[value]}</option>
              ))}
            </select>
          </label>
          {category === 'observation' ? (
            <label>
              Unit
              <input value={unit} onChange={(event) => {
                setUnit(event.target.value)
                setError('')
              }} placeholder="e.g. mg/dL" />
            </label>
          ) : null}
        </div>

        {error ? <div className="form-error" role="alert">{error}</div> : null}

        <footer>
          <button className="secondary-button" disabled={saving} type="button" onClick={() => onKeepForReview(suggestion, category)}>{reviewLabel}</button>
          {canCreateSupportedTerm ? (
            <button className="primary-button" disabled={saving} type="button" onClick={() => void createSupportedTerm()}>
              {saving ? 'Adding term…' : 'Use for screening'}
            </button>
          ) : null}
        </footer>
      </form>
    </dialog>
  )
}
