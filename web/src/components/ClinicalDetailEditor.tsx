import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'

import type {
  BiologicalSex,
  ClinicalDetailValue,
  Fact,
  PatientFactCatalogEntry,
  PatientFactGroup,
  PatientUnsupportedDetailCategory,
} from '../api/client'
import { todayIsoDate } from '../utils/dates'

export type ClinicalDetailSubmission = {
  catalogKey: string
  value: ClinicalDetailValue
}

export type UnsupportedDetailSubmission = {
  category: PatientUnsupportedDetailCategory
  label: string
  context: string | null
}

type ClinicalDetailEditorProps = {
  open: boolean
  entries: PatientFactCatalogEntry[]
  fact: Fact | null
  error: string
  notice: string
  saving: boolean
  hasUnsavedChanges: boolean
  biologicalSex: BiologicalSex | null
  onCancel: () => void
  onDirtyChange: (dirty: boolean) => void
  onReload: () => void
  onSubmit: (submission: ClinicalDetailSubmission) => void
  onSubmitUnsupported: (submission: UnsupportedDetailSubmission) => void
}

const groupLabels: Record<PatientFactGroup | 'all', string> = {
  all: 'All',
  conditions: 'Conditions',
  medications: 'Medications',
  observations: 'Labs and observations',
}

function entryForFact(entries: PatientFactCatalogEntry[], fact: Fact | null) {
  return fact
    ? entries.find(
        (entry) => entry.fact_type === fact.fact_type && entry.concept === fact.concept,
      ) ?? null
    : null
}

function editableNumericValue(value: string | null | undefined) {
  if (!value) return ''
  const parsed = Number(value)
  return Number.isFinite(parsed) ? String(parsed) : value
}

function initialFields(entry: PatientFactCatalogEntry | null, fact: Fact | null) {
  return {
    assertion: fact?.assertion ?? 'present',
    numericValue: editableNumericValue(fact?.value_numeric),
    effectiveDate:
      fact?.effective_date ?? (entry?.effective_date_required ? todayIsoDate() : ''),
  }
}

export function ClinicalDetailEditor({
  open,
  entries,
  fact,
  error,
  notice,
  saving,
  hasUnsavedChanges,
  biologicalSex,
  onCancel,
  onDirtyChange,
  onReload,
  onSubmit,
  onSubmitUnsupported,
}: ClinicalDetailEditorProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)
  const editingEntry = entryForFact(entries, fact)
  const [selectedKey, setSelectedKey] = useState('')
  const [query, setQuery] = useState('')
  const [group, setGroup] = useState<PatientFactGroup | 'all'>('all')
  const [assertion, setAssertion] = useState<Fact['assertion']>('present')
  const [numericValue, setNumericValue] = useState('')
  const [effectiveDate, setEffectiveDate] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [unsupportedMode, setUnsupportedMode] = useState(false)
  const [unsupportedCategory, setUnsupportedCategory] =
    useState<PatientUnsupportedDetailCategory>('condition')
  const [unsupportedLabel, setUnsupportedLabel] = useState('')
  const [unsupportedContext, setUnsupportedContext] = useState('')
  const selectedEntry =
    editingEntry ?? entries.find((entry) => entry.key === selectedKey) ?? null

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      returnFocusRef.current = document.activeElement as HTMLElement | null
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
      window.requestAnimationFrame(() => {
        dialog
          .querySelector<HTMLElement>(
            '[autofocus]:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)',
          )
          ?.focus()
      })
    }
    if (!open && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
      returnFocusRef.current?.focus()
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const initial = initialFields(editingEntry, fact)
    setSelectedKey(editingEntry?.key ?? '')
    setQuery('')
    setGroup('all')
    setAssertion(initial.assertion)
    setNumericValue(initial.numericValue)
    setEffectiveDate(initial.effectiveDate)
    setFieldError('')
    setUnsupportedMode(false)
    setUnsupportedCategory('condition')
    setUnsupportedLabel('')
    setUnsupportedContext('')
    onDirtyChange(false)
  }, [editingEntry, fact, onDirtyChange, open])

  const availableEntries = useMemo(() => {
    const term = query.trim().toLowerCase()
    return entries.filter(
      (entry) =>
        (group === 'all' || entry.group === group) &&
        (!term ||
          `${entry.display_label} ${entry.help_text}`.toLowerCase().includes(term)),
    )
  }, [entries, group, query])

  const updateDirty = (
    nextAssertion: Fact['assertion'],
    nextNumericValue: string,
    nextDate: string,
    nextKey = selectedKey,
  ) => {
    if (!fact) {
      onDirtyChange(Boolean(nextKey))
      return
    }
    onDirtyChange(
      nextAssertion !== fact.assertion ||
        nextNumericValue !== editableNumericValue(fact.value_numeric) ||
        (nextDate || null) !== fact.effective_date,
    )
  }

  const selectEntry = (entry: PatientFactCatalogEntry) => {
    const initial = initialFields(entry, null)
    const initialAssertion =
      entry.input_kind === 'pregnancy_status' && biologicalSex === 'male'
        ? 'unknown'
        : initial.assertion
    setSelectedKey(entry.key)
    setAssertion(initialAssertion)
    setNumericValue(initial.numericValue)
    setEffectiveDate(initial.effectiveDate)
    setFieldError('')
    updateDirty(initialAssertion, initial.numericValue, initial.effectiveDate, entry.key)
  }

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (unsupportedMode) {
      const label = unsupportedLabel.trim()
      if (!label) {
        setFieldError('Enter the clinical detail that is missing from the catalog.')
        return
      }
      setFieldError('')
      onSubmitUnsupported({
        category: unsupportedCategory,
        label,
        context: unsupportedContext.trim() || null,
      })
      return
    }
    if (!selectedEntry) {
      setFieldError('Choose a clinical detail.')
      return
    }
    if (selectedEntry.effective_date_required && !effectiveDate) {
      setFieldError('Enter the assessment or result date.')
      return
    }
    let value: ClinicalDetailValue
    if (selectedEntry.input_kind === 'numeric') {
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
    } else if (selectedEntry.input_kind === 'pregnancy_status') {
      value = {
        input_kind: 'pregnancy_status',
        assertion,
        effective_date: effectiveDate,
      }
    } else {
      value = {
        input_kind: 'status',
        assertion,
        effective_date: effectiveDate || null,
      }
    }
    setFieldError('')
    onSubmit({ catalogKey: selectedEntry.key, value })
  }

  const statusOptions =
    selectedEntry?.input_kind === 'pregnancy_status'
      ? [
          ['present', 'Pregnant'],
          ['absent', 'Not pregnant'],
          ['unknown', 'Unknown'],
        ] as const
      : [
          ['present', selectedEntry?.input_kind === 'numeric' ? 'Result available' : 'Present'],
          ['absent', 'Absent'],
          ['unknown', 'Unknown'],
        ] as const
  const visibleStatusOptions = statusOptions.filter(([value]) =>
    selectedEntry?.allowed_assertions.includes(value),
  )
  const pregnancyForMale =
    selectedEntry?.input_kind === 'pregnancy_status' && biologicalSex === 'male'
  const pregnancyWithoutSex =
    selectedEntry?.input_kind === 'pregnancy_status' &&
    biologicalSex === null &&
    assertion === 'present'

  return (
    <dialog
      ref={dialogRef}
      className="clinical-detail-dialog"
      aria-labelledby="clinical-detail-editor-title"
      onCancel={(event) => {
        event.preventDefault()
        if (!saving) onCancel()
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && !saving) {
          event.preventDefault()
          onCancel()
        }
      }}
    >
      <form noValidate onSubmit={submit}>
        <header className="clinical-detail-dialog-head">
          <div>
            <h2 id="clinical-detail-editor-title">
              {fact ? `Edit ${editingEntry?.display_label ?? 'clinical detail'}` : 'Add clinical detail'}
            </h2>
          </div>
          <button
            aria-label="Close clinical detail editor"
            className="dialog-close"
            disabled={saving}
            type="button"
            onClick={onCancel}
          >
            ×
          </button>
        </header>

        {!fact && unsupportedMode ? (
          <div className="clinical-detail-fields unsupported-detail-fields">
            <button
              className="back-to-catalog"
              type="button"
              onClick={() => {
                setUnsupportedMode(false)
                setFieldError('')
                onDirtyChange(false)
              }}
            >
              ← Choose a supported detail
            </button>
            <div className="selected-catalog-detail unsupported-review-heading">
              <div>
                <span>Review item</span>
                <strong>Detail not listed</strong>
              </div>
              <p>
                Record it for follow-up. It will be visible on this patient but will not
                be used as screening evidence.
              </p>
            </div>
            <fieldset className="detail-status-field">
              <legend>Closest category</legend>
              <div>
                {([
                  ['condition', 'Condition'],
                  ['medication', 'Medication'],
                  ['observation', 'Lab or observation'],
                  ['other', 'Other'],
                ] as const).map(([value, label]) => (
                  <label key={value}>
                    <input
                      checked={unsupportedCategory === value}
                      name="unsupported-category"
                      type="radio"
                      value={value}
                      onChange={() => {
                        setUnsupportedCategory(value)
                        setFieldError('')
                        onDirtyChange(Boolean(unsupportedLabel.trim() || unsupportedContext.trim()))
                      }}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <label>
              Clinical detail
              <input
                autoFocus
                maxLength={160}
                value={unsupportedLabel}
                onChange={(event) => {
                  setUnsupportedLabel(event.target.value)
                  setFieldError('')
                  onDirtyChange(Boolean(event.target.value.trim() || unsupportedContext.trim()))
                }}
                placeholder="Enter the missing medication, condition, or result"
              />
            </label>
            <label>
              Context
              <textarea
                maxLength={500}
                rows={3}
                value={unsupportedContext}
                onChange={(event) => {
                  setUnsupportedContext(event.target.value)
                  setFieldError('')
                  onDirtyChange(Boolean(unsupportedLabel.trim() || event.target.value.trim()))
                }}
                placeholder="Optional note for later catalog review"
              />
              <small>Optional · not screening evidence</small>
            </label>
          </div>
        ) : !fact && !selectedEntry ? (
          <div className="catalog-browser">
            <label className="catalog-search">
              Search supported details
              <input
                autoFocus
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search conditions, medications, or labs"
              />
            </label>
            <div className="catalog-groups" aria-label="Clinical detail groups">
              {(Object.keys(groupLabels) as Array<PatientFactGroup | 'all'>).map((key) => (
                <button
                  aria-pressed={group === key}
                  className={group === key ? 'selected' : ''}
                  key={key}
                  type="button"
                  onClick={() => setGroup(key)}
                >
                  {groupLabels[key]}
                </button>
              ))}
            </div>
            <div className="catalog-options" aria-label="Supported clinical details">
              {availableEntries.map((entry) => (
                <button key={entry.key} type="button" onClick={() => selectEntry(entry)}>
                  <strong>{entry.display_label}</strong>
                  <span>{groupLabels[entry.group]}</span>
                  {entry.fixed_unit ? <small>{entry.fixed_unit}</small> : null}
                </button>
              ))}
              {availableEntries.length === 0 ? (
                <div className="catalog-empty">
                  <strong>No supported details match</strong>
                  <span>Try another search or group.</span>
                </div>
              ) : null}
            </div>
            <button
              className="unsupported-detail-entry"
              type="button"
              onClick={() => {
                setUnsupportedMode(true)
                setFieldError('')
                onDirtyChange(false)
              }}
            >
              <strong>Detail not listed?</strong>
              <span>Record it for review without using it as screening evidence.</span>
            </button>
          </div>
        ) : selectedEntry ? (
          <div className="clinical-detail-fields">
            {!fact ? (
              <button
                className="back-to-catalog"
                type="button"
                onClick={() => {
                  setSelectedKey('')
                  onDirtyChange(false)
                }}
              >
                ← Choose another detail
              </button>
            ) : null}
            <div className="selected-catalog-detail">
              <div>
                <span>{groupLabels[selectedEntry.group]}</span>
                <strong>{selectedEntry.display_label}</strong>
              </div>
              <p>{selectedEntry.help_text}</p>
            </div>
            <fieldset className="detail-status-field">
              <legend>
                {selectedEntry.input_kind === 'numeric' ? 'Result status' : 'Status'}
              </legend>
              <div>
                {visibleStatusOptions.map(([value, label]) => (
                  <label key={value}>
                    <input
                      checked={assertion === value}
                      disabled={pregnancyForMale && value === 'present'}
                      name="detail-status"
                      type="radio"
                      value={value}
                      onChange={() => {
                        setAssertion(value)
                        setFieldError('')
                        updateDirty(value, numericValue, effectiveDate)
                      }}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            {pregnancyForMale ? (
              <div className="detail-consistency-hint" role="note">
                Pregnant is unavailable because biological sex is recorded as Male.
                Not pregnant and Unknown remain explicit evidence choices.
              </div>
            ) : null}
            {pregnancyWithoutSex ? (
              <div className="detail-consistency-warning" role="status">
                Biological sex is not recorded. You can save Pregnant, but the
                demographic profile will be flagged for review.
              </div>
            ) : null}
            {selectedEntry.input_kind === 'numeric' && assertion !== 'unknown' ? (
              <label className="numeric-detail-input">
                Result
                <span>
                  <input
                    aria-label="Result"
                    autoFocus={!fact}
                    inputMode="decimal"
                    type="number"
                    step="any"
                    value={numericValue}
                    onChange={(event) => {
                      setNumericValue(event.target.value)
                      setFieldError('')
                      updateDirty(assertion, event.target.value, effectiveDate)
                    }}
                  />
                  <strong>{selectedEntry.fixed_unit}</strong>
                </span>
              </label>
            ) : null}
            <label>
              {selectedEntry.input_kind === 'numeric' ? 'Result date' : 'Assessed date'}
              <input
                type="date"
                required={selectedEntry.effective_date_required}
                value={effectiveDate}
                onChange={(event) => {
                  setEffectiveDate(event.target.value)
                  setFieldError('')
                  updateDirty(assertion, numericValue, event.target.value)
                }}
              />
              {!selectedEntry.effective_date_required ? (
                <small>Optional</small>
              ) : null}
            </label>
          </div>
        ) : null}

        {notice ? <div className="detail-editor-notice" role="status">{notice}</div> : null}
        {fieldError || error ? (
          <div className="form-error detail-editor-error" role="alert">
            <span>{fieldError || error}</span>
            {error.includes('changed after') ? (
              <button className="text-button" type="button" onClick={onReload}>
                Reload current record
              </button>
            ) : null}
          </div>
        ) : null}
        <footer className="clinical-detail-dialog-actions">
          <button className="secondary-button" disabled={saving} type="button" onClick={onCancel}>
            Cancel
          </button>
          {selectedEntry || unsupportedMode ? (
            <button
              className="primary-button"
              disabled={saving || !hasUnsavedChanges}
              type="submit"
            >
              {saving
                ? 'Saving…'
                : unsupportedMode
                  ? 'Save for review'
                  : fact
                    ? 'Save changes'
                    : 'Add detail'}
            </button>
          ) : null}
        </footer>
      </form>
    </dialog>
  )
}
