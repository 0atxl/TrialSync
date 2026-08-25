import { type PatientFactCatalogEntry, type TrialImportCriterion } from '../api/client'
import { importedCriterionIsReady } from '../utils/importCriteria'
import { StateMessage } from './UiPrimitives'

type TrialCandidatesProps = {
  kind: 'inclusion' | 'exclusion'
  criteria: TrialImportCriterion[]
  catalog: PatientFactCatalogEntry[]
  update: (id: string, values: Partial<TrialImportCriterion>) => void
}

export function TrialImportCandidates({
  kind,
  criteria,
  catalog,
  update,
}: TrialCandidatesProps) {
  if (!criteria.length) {
    return (
      <StateMessage state="empty" title={`No ${kind} criteria found`}>
        You can continue and add criteria later.
      </StateMessage>
    )
  }

  return (
    <div className="import-candidate-list">
      {criteria.map((criterion) => (
        <ImportedCriterion
          key={criterion.candidate_id}
          criterion={criterion}
          catalog={catalog}
          update={update}
        />
      ))}
    </div>
  )
}

function ImportedCriterion({
  criterion,
  catalog,
  update,
}: {
  criterion: TrialImportCriterion
  catalog: PatientFactCatalogEntry[]
  update: TrialCandidatesProps['update']
}) {
  const rule = criterion.normalized_rule ?? {}
  const subject = typeof rule.fact === 'string'
    ? rule.fact
    : rule.op === 'concept_is' ? 'biological_sex' : ''
  const selectedKey = subject === 'demographic.age'
    ? 'age'
    : subject === 'biological_sex'
      ? 'biological_sex'
      : catalog.find((entry) => `${entry.fact_type}.${entry.concept}` === subject)?.key ?? ''
  const entry = catalog.find((item) => item.key === selectedKey)
  const numeric = selectedKey === 'age' || entry?.input_kind === 'numeric'
  const mapped = importedCriterionIsReady(criterion, catalog)

  const setRule = (normalizedRule: Record<string, unknown> | null) => {
    update(criterion.candidate_id, {
      normalized_rule: normalizedRule,
      parse_state: normalizedRule ? 'parsed' : 'needs_manual_rule',
    })
  }

  const setSubject = (key: string) => {
    if (!key) return setRule(null)
    if (key === 'age') {
      return setRule({
        op: 'between', fact: 'demographic.age', min: 18, max: 75, unit: 'year',
      })
    }
    if (key === 'biological_sex') {
      return setRule({ op: 'concept_is', fact_type: 'demographic', concept: 'female' })
    }
    const match = catalog.find((item) => item.key === key)
    if (!match) return
    setRule(match.input_kind === 'numeric'
      ? {
          op: 'between',
          fact: `${match.fact_type}.${match.concept}`,
          min: '',
          max: '',
          unit: match.fixed_unit,
        }
      : { op: 'present', fact: `${match.fact_type}.${match.concept}` })
  }

  const numericRule = (op: string) => {
    const base = { op, fact: rule.fact, ...(rule.unit ? { unit: rule.unit } : {}) }
    return op === 'between'
      ? { ...base, min: rule.min ?? '', max: rule.max ?? '' }
      : { ...base, value: rule.value ?? '' }
  }
  const numericValue = (value: string) => value === '' ? '' : Number(value)

  return (
    <article className={mapped ? '' : 'needs-mapping'}>
      <header>
        <label>
          <input
            type="checkbox"
            checked={criterion.selected}
            onChange={(event) => update(criterion.candidate_id, {
              selected: event.target.checked,
            })}
          />
          <span>
            <strong>{criterion.source_text}</strong>
            <small>{mapped ? 'Supported criterion' : 'Choose a supported criterion'}</small>
          </span>
        </label>
        {!mapped ? <span>Needs review</span> : null}
      </header>

      {criterion.selected ? (
        <div className="import-candidate-fields">
          <label>
            Criterion
            <select value={selectedKey} onChange={(event) => setSubject(event.target.value)}>
              <option value="">Choose a supported criterion</option>
              <option value="age">Age</option>
              <option value="biological_sex">Biological sex</option>
              {catalog.filter((item) => item.screening_supported).map((item) => (
                <option key={item.key} value={item.key}>{item.display_label}</option>
              ))}
            </select>
          </label>
          {selectedKey === 'biological_sex' ? (
            <label>
              Required value
              <select
                value={String(rule.concept ?? 'female')}
                onChange={(event) => setRule({
                  op: 'concept_is', fact_type: 'demographic', concept: event.target.value,
                })}
              >
                <option value="female">Female</option>
                <option value="male">Male</option>
              </select>
            </label>
          ) : numeric ? (
            <>
              <label>
                Comparison
                <select
                  value={String(rule.op ?? 'between')}
                  onChange={(event) => setRule(numericRule(event.target.value))}
                >
                  <option value="gte">At least</option>
                  <option value="lte">At most</option>
                  <option value="between">Between</option>
                </select>
              </label>
              {rule.op === 'between' ? (
                <div className="form-pair">
                  <label>
                    Minimum
                    <input
                      type="number"
                      step="any"
                      value={String(rule.min ?? '')}
                      onChange={(event) => setRule({
                        ...rule, min: numericValue(event.target.value),
                      })}
                    />
                  </label>
                  <label>
                    Maximum
                    <input
                      type="number"
                      step="any"
                      value={String(rule.max ?? '')}
                      onChange={(event) => setRule({
                        ...rule, max: numericValue(event.target.value),
                      })}
                    />
                  </label>
                </div>
              ) : (
                <label>
                  Threshold
                  <input
                    type="number"
                    step="any"
                    value={String(rule.value ?? '')}
                    onChange={(event) => setRule({
                      ...rule, value: numericValue(event.target.value),
                    })}
                  />
                </label>
              )}
            </>
          ) : selectedKey ? (
            <label>
              Required state
              <select
                value={String(rule.op ?? 'present')}
                onChange={(event) => setRule({
                  op: event.target.value, fact: rule.fact,
                })}
              >
                <option value="present">Present</option>
                <option value="absent">Absent</option>
              </select>
            </label>
          ) : null}
        </div>
      ) : null}

      <details className="source-note">
        <summary>Source wording</summary>
        <q>{criterion.source.text}</q>
      </details>
      {criterion.warnings.length ? (
        <ul className="candidate-warning-list">
          {criterion.warnings.map((warning) => <li key={warning}>{warning}</li>)}
        </ul>
      ) : null}
    </article>
  )
}
