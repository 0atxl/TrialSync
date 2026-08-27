import type { CriterionEvaluation, Evidence } from '../api/client'
import { isConfigurationReason, reasonLabel } from '../pages/screeningHelpers'

const groupOrder = ['fail', 'unknown', 'pass'] as const

const groupLabels = {
  fail: 'Not met',
  unknown: 'Needs review',
  pass: 'Satisfied',
}

const resultLabels = {
  fail: 'Not met',
  unknown: 'Review',
  pass: 'Satisfied',
}

function evidenceValue(item: Evidence) {
  return [item.value ?? 'Recorded detail', item.unit, item.effective_date]
    .filter(Boolean)
    .join(' · ')
}

function EvaluationRow({ evaluation }: { evaluation: CriterionEvaluation }) {
  const configurationIssue = isConfigurationReason(evaluation.reason_code)

  return (
    <details
      className={`evaluation evaluation-${evaluation.result}`}
      id={`criterion-${evaluation.id}`}
      role="article"
      tabIndex={-1}
    >
      <summary className="evaluation-head">
        <span className="criterion-order">{evaluation.criterion_order}</span>
        <div>
          <span className="record-kind">
            {evaluation.criterion_kind === 'inclusion' ? 'Inclusion' : 'Exclusion'}
          </span>
          <h3>{evaluation.criterion_source_text}</h3>
        </div>
        <span className={`state state-${evaluation.result}`}>
          {resultLabels[evaluation.result]}
        </span>
      </summary>
      <div className="evaluation-detail">
        <p className="canonical">{evaluation.canonical_explanation}</p>
        <div className="evidence-grid">
          <div>
            <strong>Assessment</strong>
            <p>{reasonLabel(evaluation.reason_code)}</p>
          </div>
          <div>
            <strong>{configurationIssue ? 'Required action' : 'Recorded evidence'}</strong>
            {configurationIssue ? <p>Correct this trial criterion and run a new screening.</p> : evaluation.evidence.length ? <ul>{evaluation.evidence.map((evidence, index) => <li key={`${evidence.fact_id}-${index}`}>{evidenceValue(evidence)}{evidence.source_label ? <small>{evidence.source_label}</small> : null}</li>)}</ul> : <p>No supporting information was recorded.</p>}
          </div>
          {evaluation.missing_information.length > 0 ? <div><strong>Information needed</strong><ul>{evaluation.missing_information.map((missing, index) => <li key={`${missing.fact}-${index}`}>{missing.detail || 'Additional information is required.'}</li>)}</ul></div> : null}
        </div>
      </div>
    </details>
  )
}

export function ScreeningEvidence({ evaluations }: { evaluations: CriterionEvaluation[] }) {
  return (
    <section className="criteria-section" aria-labelledby="screening-evidence-heading">
      <div className="section-heading">
        <h2 id="screening-evidence-heading">Eligibility evidence</h2>
      </div>
      <div className="evaluation-groups">
        {groupOrder.map((result) => {
          const items = evaluations
            .filter((evaluation) => evaluation.result === result)
            .sort((left, right) => left.criterion_order - right.criterion_order)
          if (items.length === 0) return null
          return (
            <section className={`evaluation-group evaluation-group-${result}`} key={result}>
              <header>
                <h3>{groupLabels[result]}</h3>
                <span>{items.length}</span>
              </header>
              {items.map((evaluation) => (
                <EvaluationRow evaluation={evaluation} key={evaluation.id} />
              ))}
            </section>
          )
        })}
      </div>
    </section>
  )
}
