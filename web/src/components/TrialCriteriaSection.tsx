import type { Criterion, PatientFactCatalogEntry } from '../api/client'
import { criterionSubjectKey } from './TrialCriterionEditor'

type TrialCriteriaSectionProps = {
  currentProtocol: boolean
  criteriaByKind: Record<Criterion['kind'], Criterion[]>
  editing: boolean
  saving: boolean
  catalogError: string
  canSave: boolean
  onAdd: (kind: Criterion['kind']) => void
  onEdit: (criterion: Criterion) => void
  onRemove: (criterion: Criterion) => void
  onSave: () => void
  onStartEditing: () => void
  catalog: PatientFactCatalogEntry[]
}

export function TrialCriteriaSection({
  currentProtocol,
  criteriaByKind,
  editing,
  saving,
  catalogError,
  canSave,
  onAdd,
  onEdit,
  onRemove,
  onSave,
  onStartEditing,
  catalog,
}: TrialCriteriaSectionProps) {
  return (
    <section className="trial-criteria-workspace" aria-labelledby="trial-criteria-heading">
      <div className="clinical-details-heading">
        <h2 id="trial-criteria-heading">Eligibility criteria</h2>
        {editing ? (
          <button className="primary-button" disabled={saving || !canSave} type="button" onClick={onSave}>
            {saving ? 'Saving…' : 'Save protocol'}
          </button>
        ) : (
          <button className="primary-button" disabled={saving} type="button" onClick={onStartEditing}>
            {saving ? 'Opening…' : 'Edit criteria'}
          </button>
        )}
      </div>

      {currentProtocol ? (
        <>
          {editing ? (
            <div className="draft-banner" role="status">
              <strong>Editing criteria</strong>
              <span>Save the protocol when these changes are ready.</span>
            </div>
          ) : null}
          <div className="trial-criteria-groups">
            {(['inclusion', 'exclusion'] as const).map((kind) => (
              <section className={`trial-criterion-group criterion-${kind}`} key={kind}>
                <header>
                  <div>
                    <h3>{kind === 'inclusion' ? 'Inclusion criteria' : 'Exclusion criteria'}</h3>
                    <span>{criteriaByKind[kind].length}</span>
                  </div>
                  <button
                    className="secondary-button"
                    disabled={!editing || Boolean(catalogError)}
                    type="button"
                    onClick={() => onAdd(kind)}
                  >
                    Add criterion
                  </button>
                </header>
                {criteriaByKind[kind].length === 0 ? (
                  <div className="trial-criterion-empty">No {kind} criteria have been added.</div>
                ) : (
                  <div className="trial-criterion-rows">
                    {criteriaByKind[kind].map((criterion) => {
                      const supported = Boolean(
                        criterion.normalized_rule && criterionSubjectKey(criterion, catalog),
                      )
                      return (
                        <article className="trial-criterion-row" key={criterion.id}>
                          <div>
                            <strong>{criterion.source_text}</strong>
                            {!supported ? <span>Needs mapping before use</span> : null}
                          </div>
                          <div className="record-actions">
                            {editing && supported ? (
                              <button className="text-button" type="button" onClick={() => onEdit(criterion)}>Edit</button>
                            ) : !supported ? (
                              <span className="unsupported-detail">Needs mapping</span>
                            ) : null}
                            {editing ? (
                              <button
                                className="text-button danger"
                                disabled={saving}
                                type="button"
                                onClick={() => onRemove(criterion)}
                              >
                                Remove
                              </button>
                            ) : null}
                          </div>
                        </article>
                      )
                    })}
                  </div>
                )}
              </section>
            ))}
          </div>
        </>
      ) : (
        <div className="trial-draft-empty">
          <strong>No eligibility criteria yet.</strong>
          <p>Select Edit criteria to add inclusion and exclusion criteria.</p>
        </div>
      )}
    </section>
  )
}
