import { type PatientFactCatalogEntry, type PatientImportFact } from '../api/client'
import { todayIsoDate } from '../utils/dates'
import { StateMessage } from './UiPrimitives'

type PatientCandidatesProps = {
  facts: PatientImportFact[]
  catalog: PatientFactCatalogEntry[]
  update: (id: string, values: Partial<PatientImportFact>) => void
}
function catalogEntryForFact(
  fact: PatientImportFact,
  catalog: PatientFactCatalogEntry[],
) {
  return catalog.find((entry) =>
    entry.fact_type === fact.fact_type
    && entry.concept.toLowerCase() === fact.concept.toLowerCase(),
  )
}

function patientFactReady(
  fact: PatientImportFact,
  entry: PatientFactCatalogEntry | undefined,
) {
  if (!entry) return false
  if (entry.effective_date_required && !fact.effective_date) return false
  return entry.input_kind !== 'numeric'
    || fact.assertion === 'unknown'
    || fact.value_numeric !== null
}

export function PatientImportCandidates({ facts, catalog, update }: PatientCandidatesProps) {
  if (!facts.length) {
    return (
      <StateMessage state="empty" title="No clinical details found">
        You can create the patient and add details later.
      </StateMessage>
    )
  }

  return (
    <div className="import-candidate-list">
      {facts.map((fact) => {
        const entry = catalogEntryForFact(fact, catalog)
        const ready = patientFactReady(fact, entry)
        return (
          <article className={ready ? '' : 'needs-mapping'} key={fact.candidate_id}>
            <header>
              <label>
                <input
                  type="checkbox"
                  checked={fact.selected}
                  onChange={(event) => update(fact.candidate_id, {
                    selected: event.target.checked,
                  })}
                />
                <span>
                  <strong>{entry?.display_label ?? fact.concept.replaceAll('_', ' ')}</strong>
                  <small>{ready ? 'Ready to use' : 'Complete or keep for review'}</small>
                </span>
              </label>
              {!ready ? <span>Needs review</span> : null}
            </header>

            {fact.selected ? (
              <div className="import-candidate-fields">
                <label>
                  Clinical detail
                  <select
                    value={entry?.key ?? ''}
                    onChange={(event) => {
                      const match = catalog.find((item) => item.key === event.target.value)
                      if (match) {
                        update(fact.candidate_id, {
                          fact_type: match.fact_type,
                          concept: match.concept,
                          unit: match.fixed_unit,
                          value_text: null,
                        })
                      }
                    }}
                  >
                    <option value="">Choose an available detail</option>
                    {catalog.map((item) => (
                      <option key={item.key} value={item.key}>{item.display_label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Status
                  <select
                    value={fact.assertion}
                    onChange={(event) => update(fact.candidate_id, {
                      assertion: event.target.value as PatientImportFact['assertion'],
                    })}
                  >
                    <option value="present">Present</option>
                    <option value="absent">Absent</option>
                    <option value="unknown">Unknown</option>
                  </select>
                </label>
                {entry?.input_kind === 'numeric' ? (
                  <label>
                    Result
                    <div className="input-with-unit">
                      <input
                        inputMode="decimal"
                        value={fact.value_numeric ?? ''}
                        onChange={(event) => update(fact.candidate_id, {
                          value_numeric: event.target.value || null,
                        })}
                      />
                      <strong>{entry.fixed_unit}</strong>
                    </div>
                  </label>
                ) : null}
                <label>
                  {entry?.input_kind === 'numeric' ? 'Result date' : 'Assessed date'}
                  <input
                    max={todayIsoDate()}
                    type="date"
                    value={fact.effective_date ?? ''}
                    onChange={(event) => update(fact.candidate_id, {
                      effective_date: event.target.value || null,
                    })}
                  />
                </label>
              </div>
            ) : null}

            <details className="source-note">
              <summary>Source wording</summary>
              <q>{fact.source.text}</q>
            </details>
            {fact.warnings.length ? (
              <ul className="candidate-warning-list">
                {fact.warnings.map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            ) : null}
          </article>
        )
      })}
    </div>
  )
}
