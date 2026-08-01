import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'

import type {
  BiologicalSex,
  Criterion,
  PatientFactCatalogEntry,
  PatientFactGroup,
} from '../api/client'

export type GuidedCriterionSubmission = {
  kind: Criterion['kind']
  subject_key: string
  operator: 'present' | 'absent' | 'gte' | 'lte' | 'between' | 'is'
  value: number | null
  minimum: number | null
  maximum: number | null
  biological_sex: BiologicalSex | null
}

export type UnsupportedCriterionSubmission = {
  kind: Criterion['kind']
  category: 'demographic' | 'condition' | 'medication' | 'observation' | 'other'
  source_text: string
}

type CriterionDraft = {
  kind: Criterion['kind']
  subjectKey: string
  operator: GuidedCriterionSubmission['operator']
  value: string
  minimum: string
  maximum: string
  biologicalSex: BiologicalSex
}

type TrialCriterionEditorProps = {
  open: boolean
  entries: PatientFactCatalogEntry[]
  criterion: Criterion | null
  initialKind: Criterion['kind']
  saving: boolean
  error: string
  onCancel: () => void
  onSubmit: (submission: GuidedCriterionSubmission) => void
  onSubmitUnsupported: (submission: UnsupportedCriterionSubmission) => void
}

const groupLabels: Record<PatientFactGroup | 'demographics' | 'all', string> = {
  all: 'All',
  demographics: 'Demographics',
  conditions: 'Conditions',
  medications: 'Medications',
  observations: 'Labs and observations',
}

function factKey(entry: PatientFactCatalogEntry) {
  return `${entry.fact_type}.${entry.concept}`
}

// This parsing helper is shared with the trial detail list.
// eslint-disable-next-line react-refresh/only-export-components
export function criterionSubjectKey(
  criterion: Criterion,
  entries: PatientFactCatalogEntry[],
) {
  const rule = criterion.normalized_rule
  if (!rule) return null
  if (rule.fact === 'demographic.age') return 'age'
  if (
    rule.op === 'concept_is' &&
    rule.fact_type === 'demographic' &&
    (rule.concept === 'male' || rule.concept === 'female')
  ) return 'biological_sex'
  if (typeof rule.fact !== 'string') return null
  return entries.find((entry) => factKey(entry) === rule.fact)?.key ?? null
}

function draftForCriterion(
  criterion: Criterion | null,
  entries: PatientFactCatalogEntry[],
  initialKind: Criterion['kind'],
): CriterionDraft {
  if (!criterion) {
    return {
      kind: initialKind,
      subjectKey: '',
      operator: 'present',
      value: '',
      minimum: '',
      maximum: '',
      biologicalSex: 'female',
    }
  }
  const rule = criterion.normalized_rule ?? {}
  const subjectKey = criterionSubjectKey(criterion, entries) ?? ''
  const operator =
    rule.op === 'concept_is'
      ? 'is'
      : ['present', 'absent', 'gte', 'lte', 'between'].includes(String(rule.op))
        ? rule.op as CriterionDraft['operator']
        : 'present'
  return {
    kind: criterion.kind,
    subjectKey,
    operator,
    value: rule.value === undefined ? '' : String(rule.value),
    minimum: rule.min === undefined ? '' : String(rule.min),
    maximum: rule.max === undefined ? '' : String(rule.max),
    biologicalSex: rule.concept === 'male' ? 'male' : 'female',
  }
}

function subjectLabel(
  key: string,
  entries: PatientFactCatalogEntry[],
) {
  if (key === 'age') return 'Age'
  if (key === 'biological_sex') return 'Biological sex'
  return entries.find((entry) => entry.key === key)?.display_label ?? 'Criterion'
}

function defaultOperator(key: string, entries: PatientFactCatalogEntry[]) {
  if (key === 'age') return 'between'
  if (key === 'biological_sex') return 'is'
  return entries.find((entry) => entry.key === key)?.input_kind === 'numeric'
    ? 'between'
    : 'present'
}

export function TrialCriterionEditor({
  open,
  entries,
  criterion,
  initialKind,
  saving,
  error,
  onCancel,
  onSubmit,
  onSubmitUnsupported,
}: TrialCriterionEditorProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)
  const [draft, setDraft] = useState(() =>
    draftForCriterion(criterion, entries, initialKind))
  const [query, setQuery] = useState('')
  const [group, setGroup] = useState<PatientFactGroup | 'demographics' | 'all'>('all')
  const [fieldError, setFieldError] = useState('')
  const [unsupportedMode, setUnsupportedMode] = useState(false)
  const [unsupportedCategory, setUnsupportedCategory] =
    useState<UnsupportedCriterionSubmission['category']>('condition')
  const [unsupportedText, setUnsupportedText] = useState('')

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      returnFocusRef.current = document.activeElement as HTMLElement | null
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
      window.requestAnimationFrame(() => {
        dialog.querySelector<HTMLElement>('[autofocus], input, select, textarea')?.focus()
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
    setDraft(draftForCriterion(criterion, entries, initialKind))
    setQuery('')
    setGroup('all')
    setFieldError('')
    setUnsupportedMode(false)
    setUnsupportedCategory('condition')
    setUnsupportedText('')
  }, [criterion, entries, initialKind, open])

  const subjects = useMemo(() => {
    const all = [
      {
        key: 'age',
        label: 'Age',
        group: 'demographics' as const,
        help: 'Set an age minimum, maximum, or range.',
        unit: 'years',
      },
      {
        key: 'biological_sex',
        label: 'Biological sex',
        group: 'demographics' as const,
        help: 'Choose Male or Female for screening.',
        unit: null,
      },
      ...entries.filter((entry) => entry.screening_supported).map((entry) => ({
        key: entry.key,
        label: entry.display_label,
        group: entry.group,
        help: entry.help_text,
        unit: entry.fixed_unit,
      })),
    ]
    const term = query.trim().toLowerCase()
    return all.filter((subject) =>
      (group === 'all' || subject.group === group) &&
      (!term || `${subject.label} ${subject.help}`.toLowerCase().includes(term)))
  }, [entries, group, query])

  const selectedEntry = entries.find((entry) => entry.key === draft.subjectKey) ?? null
  const isNumeric = draft.subjectKey === 'age' || selectedEntry?.input_kind === 'numeric'
  const isSex = draft.subjectKey === 'biological_sex'
  const hasSubject = Boolean(draft.subjectKey)

  const update = (values: Partial<CriterionDraft>) => {
    setDraft((current) => ({ ...current, ...values }))
    setFieldError('')
  }

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (unsupportedMode) {
      if (!unsupportedText.trim()) {
        setFieldError('Enter the unsupported criterion wording.')
        return
      }
      onSubmitUnsupported({
        kind: draft.kind,
        category: unsupportedCategory,
        source_text: unsupportedText.trim(),
      })
      return
    }
    if (!draft.subjectKey) {
      setFieldError('Choose a criterion.')
      return
    }
    const value = draft.value.trim() === '' ? null : Number(draft.value)
    const minimum = draft.minimum.trim() === '' ? null : Number(draft.minimum)
    const maximum = draft.maximum.trim() === '' ? null : Number(draft.maximum)
    if (
      isNumeric &&
      ((draft.operator === 'between' &&
        (minimum === null || maximum === null || minimum > maximum)) ||
        (draft.operator !== 'between' && value === null))
    ) {
      setFieldError(
        draft.operator === 'between'
          ? 'Enter a range with the minimum at or below the maximum.'
          : 'Enter a numeric threshold.',
      )
      return
    }
    onSubmit({
      kind: draft.kind,
      subject_key: draft.subjectKey,
      operator: draft.operator,
      value,
      minimum,
      maximum,
      biological_sex: isSex ? draft.biologicalSex : null,
    })
  }

  return (
    <dialog
      ref={dialogRef}
      className="clinical-detail-dialog trial-criterion-dialog"
      aria-labelledby="trial-criterion-editor-title"
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
            <p className="eyebrow">{criterion ? 'Edit criterion' : 'Controlled criterion'}</p>
            <h2 id="trial-criterion-editor-title">
              {criterion
                ? `Edit ${subjectLabel(draft.subjectKey, entries)}`
                : `Add ${draft.kind} criterion`}
            </h2>
          </div>
          <button
            aria-label="Close criterion editor"
            className="dialog-close"
            disabled={saving}
            type="button"
            onClick={onCancel}
          >
            ×
          </button>
        </header>

        {unsupportedMode ? (
          <div className="clinical-detail-fields unsupported-detail-fields">
            <button
              className="back-to-catalog"
              type="button"
              onClick={() => {
                setUnsupportedMode(false)
                setFieldError('')
              }}
            >
              ← Choose a supported criterion
            </button>
            <div className="selected-catalog-detail unsupported-review-heading">
              <div>
                <span>Review required</span>
                <strong>Unsupported criterion</strong>
              </div>
              <p>
                Preserve the protocol wording for review. The protocol cannot be saved
                until this criterion is mapped or removed.
              </p>
            </div>
            <fieldset className="detail-status-field">
              <legend>Criterion section</legend>
              <div>
                {(['inclusion', 'exclusion'] as const).map((kind) => (
                  <label key={kind}>
                    <input
                      checked={draft.kind === kind}
                      name="unsupported-criterion-kind"
                      type="radio"
                      onChange={() => update({ kind })}
                    />
                    <span>{kind === 'inclusion' ? 'Inclusion' : 'Exclusion'}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <label>
              Closest category
              <select
                value={unsupportedCategory}
                onChange={(event) =>
                  setUnsupportedCategory(
                    event.target.value as UnsupportedCriterionSubmission['category'],
                  )}
              >
                <option value="demographic">Demographic</option>
                <option value="condition">Condition</option>
                <option value="medication">Medication</option>
                <option value="observation">Lab or observation</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label>
              Protocol wording
              <textarea
                autoFocus
                rows={4}
                maxLength={10_000}
                value={unsupportedText}
                onChange={(event) => {
                  setUnsupportedText(event.target.value)
                  setFieldError('')
                }}
                placeholder="Enter the criterion exactly as it should be reviewed"
              />
            </label>
          </div>
        ) : !hasSubject ? (
          <div className="catalog-browser">
            <label className="catalog-search">
              Search supported criteria
              <input
                autoFocus
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search demographics, conditions, medications, or labs"
              />
            </label>
            <div className="catalog-groups" aria-label="Criterion categories">
              {(Object.keys(groupLabels) as Array<
                PatientFactGroup | 'demographics' | 'all'
              >).map((key) => (
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
            <div className="catalog-options" aria-label="Supported trial criteria">
              {subjects.map((subject) => (
                <button
                  key={subject.key}
                  type="button"
                  onClick={() => update({
                    subjectKey: subject.key,
                    operator: defaultOperator(subject.key, entries),
                    value: '',
                    minimum: subject.key === 'age' ? '18' : '',
                    maximum: subject.key === 'age' ? '75' : '',
                  })}
                >
                  <strong>{subject.label}</strong>
                  <span>{groupLabels[subject.group]}</span>
                  {subject.unit ? <small>{subject.unit}</small> : null}
                </button>
              ))}
            </div>
            <button
              className="unsupported-detail-entry"
              type="button"
              onClick={() => {
                setUnsupportedMode(true)
                setFieldError('')
              }}
            >
              <strong>Criterion not listed?</strong>
              <span>Record its wording for review without creating a screening rule.</span>
            </button>
          </div>
        ) : (
          <div className="clinical-detail-fields">
            {!criterion ? (
              <button
                className="back-to-catalog"
                type="button"
                onClick={() => update({ subjectKey: '' })}
              >
                ← Choose another criterion
              </button>
            ) : null}
            <div className="selected-catalog-detail">
              <div>
                <span>{draft.kind} criterion</span>
                <strong>{subjectLabel(draft.subjectKey, entries)}</strong>
              </div>
              <p>The saved structured rule drives deterministic screening.</p>
            </div>
            <fieldset className="detail-status-field">
              <legend>Criterion section</legend>
              <div>
                {(['inclusion', 'exclusion'] as const).map((kind) => (
                  <label key={kind}>
                    <input
                      checked={draft.kind === kind}
                      name="criterion-kind"
                      type="radio"
                      onChange={() => update({ kind })}
                    />
                    <span>{kind === 'inclusion' ? 'Inclusion' : 'Exclusion'}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            {isSex ? (
              <fieldset className="detail-status-field">
                <legend>Required biological sex</legend>
                <div>
                  {(['female', 'male'] as const).map((sex) => (
                    <label key={sex}>
                      <input
                        checked={draft.biologicalSex === sex}
                        name="criterion-sex"
                        type="radio"
                        onChange={() => update({ biologicalSex: sex })}
                      />
                      <span>{sex === 'female' ? 'Female' : 'Male'}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : isNumeric ? (
              <>
                <fieldset className="detail-status-field">
                  <legend>Comparison</legend>
                  <div>
                    {([
                      ['gte', 'At least'],
                      ['lte', 'At most'],
                      ['between', 'Between'],
                    ] as const).map(([operator, label]) => (
                      <label key={operator}>
                        <input
                          checked={draft.operator === operator}
                          name="criterion-operator"
                          type="radio"
                          onChange={() => update({ operator })}
                        />
                        <span>{label}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
                {draft.operator === 'between' ? (
                  <div className="form-pair">
                    <label>
                      Minimum
                      <input
                        aria-label="Minimum"
                        inputMode="decimal"
                        type="number"
                        step="any"
                        value={draft.minimum}
                        onChange={(event) => update({ minimum: event.target.value })}
                      />
                    </label>
                    <label>
                      Maximum
                      <input
                        aria-label="Maximum"
                        inputMode="decimal"
                        type="number"
                        step="any"
                        value={draft.maximum}
                        onChange={(event) => update({ maximum: event.target.value })}
                      />
                    </label>
                  </div>
                ) : (
                  <label className="numeric-detail-input">
                    Threshold
                    <span>
                      <input
                        aria-label="Threshold"
                        inputMode="decimal"
                        type="number"
                        step="any"
                        value={draft.value}
                        onChange={(event) => update({ value: event.target.value })}
                      />
                      <strong>
                        {draft.subjectKey === 'age' ? 'years' : selectedEntry?.fixed_unit}
                      </strong>
                    </span>
                  </label>
                )}
                {draft.operator === 'between' ? (
                  <p className="criterion-fixed-unit">
                    Unit: {draft.subjectKey === 'age' ? 'years' : selectedEntry?.fixed_unit}
                  </p>
                ) : null}
              </>
            ) : (
              <fieldset className="detail-status-field">
                <legend>Required status</legend>
                <div>
                  {([
                    ['present', 'Present'],
                    ['absent', 'Absent'],
                  ] as const).map(([operator, label]) => (
                    <label key={operator}>
                      <input
                        checked={draft.operator === operator}
                        name="criterion-operator"
                        type="radio"
                        onChange={() => update({ operator })}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
          </div>
        )}

        {fieldError || error ? (
          <div className="form-error detail-editor-error" role="alert">
            {fieldError || error}
          </div>
        ) : null}
        <footer className="clinical-detail-dialog-actions">
          <button className="secondary-button" disabled={saving} type="button" onClick={onCancel}>
            Cancel
          </button>
          {hasSubject || unsupportedMode ? (
            <button className="primary-button" disabled={saving} type="submit">
              {saving
                ? 'Saving…'
                : unsupportedMode
                  ? 'Save for review'
                  : criterion
                    ? 'Save changes'
                    : 'Add criterion'}
            </button>
          ) : null}
        </footer>
      </form>
    </dialog>
  )
}
