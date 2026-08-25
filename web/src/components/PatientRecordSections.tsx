import type { FormEventHandler } from 'react'

import type {
  BiologicalSex,
  Fact,
  Patient,
  PatientFactCatalogEntry,
  PatientFactGroup,
} from '../api/client'
import { todayIsoDate } from '../utils/dates'
import { biologicalSexLabel } from '../utils/demographics'
import {
  clinicalGroupLabels,
  clinicalValueLabel,
  factCatalogEntry,
  factLabel,
} from '../utils/patientFacts'
import { BiologicalSexField } from './BiologicalSexField'

export type DemographicsDraft = {
  display_name: string
  date_of_birth: string
  sex: BiologicalSex | null
}

function displayValue(value: string | null) {
  return value?.trim() || 'Not recorded'
}

type DemographicsSectionProps = {
  patient: Patient
  draft: DemographicsDraft | null
  editing: boolean
  error: string
  stale: boolean
  conflictFactId: string | null
  savedChanges: string[]
  saving: boolean
  dirty: boolean
  onBeginEdit: () => void
  onCancel: () => void
  onReload: () => void
  onReviewConflict: (factId: string) => void
  onSubmit: FormEventHandler<HTMLFormElement>
  onUpdate: <Key extends keyof DemographicsDraft>(
    key: Key,
    value: DemographicsDraft[Key],
  ) => void
}

export function PatientDemographicsSection({
  patient,
  draft,
  editing,
  error,
  stale,
  conflictFactId,
  savedChanges,
  saving,
  dirty,
  onBeginEdit,
  onCancel,
  onReload,
  onReviewConflict,
  onSubmit,
  onUpdate,
}: DemographicsSectionProps) {
  return (
    <section className="demographics-panel" aria-labelledby="demographics-heading">
      <div className="demographics-heading">
        <h2 id="demographics-heading">Demographics</h2>
        {!editing ? (
          <button className="secondary-button" type="button" onClick={onBeginEdit}>
            Edit demographics
          </button>
        ) : null}
      </div>
      {editing && draft ? (
        <form className="demographics-form" noValidate onSubmit={onSubmit}>
          <div className="demographics-form-grid">
            <label>
              Display name
              <input
                required
                value={draft.display_name}
                onChange={(event) => onUpdate('display_name', event.target.value)}
              />
            </label>
            <label>
              Date of birth
              <input
                aria-describedby={error ? 'profile-error' : undefined}
                max={todayIsoDate()}
                type="date"
                value={draft.date_of_birth}
                onChange={(event) => onUpdate('date_of_birth', event.target.value)}
              />
            </label>
            <BiologicalSexField value={draft.sex} onChange={(value) => onUpdate('sex', value)} />
          </div>
          {error ? (
            <div className="form-error demographics-error" id="profile-error" role="alert">
              <span>{error}</span>
              {stale ? (
                <button className="text-button" type="button" onClick={onReload}>
                  Reload latest profile
                </button>
              ) : conflictFactId ? (
                <button
                  className="text-button"
                  type="button"
                  onClick={() => onReviewConflict(conflictFactId)}
                >
                  Review pregnancy status
                </button>
              ) : null}
            </div>
          ) : null}
          <div className="demographics-actions">
            <button className="secondary-button" disabled={saving} type="button" onClick={onCancel}>
              Cancel
            </button>
            <button className="primary-button" disabled={saving || !dirty} type="submit">
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </form>
      ) : (
        <dl className="demographics-summary">
          <div><dt>Date of birth</dt><dd>{displayValue(patient.date_of_birth)}</dd></div>
          <div><dt>Biological sex for screening</dt><dd>{biologicalSexLabel(patient.sex)}</dd></div>
        </dl>
      )}
      {savedChanges.length > 1 ? (
        <div className="change-summary" role="status">
          <strong>Patient profile updated</strong>
          <ul>{savedChanges.map((change) => <li key={change}>{change}</li>)}</ul>
        </div>
      ) : null}
    </section>
  )
}

type ClinicalDetailsSectionProps = {
  patient: Patient
  catalog: PatientFactCatalogEntry[]
  groupedFacts: Record<PatientFactGroup, Fact[]>
  query: string
  catalogLoading: boolean
  catalogError: string
  deletingFactId: string | null
  onAdd: () => void
  onEdit: (fact: Fact) => void
  onRemove: (fact: Fact) => void
  onRemoveUnsupported: (detail: Patient['unsupported_details'][number]) => void
  onQueryChange: (value: string) => void
  onReloadCatalog: () => void
}

export function PatientClinicalDetailsSection({
  patient,
  catalog,
  groupedFacts,
  query,
  catalogLoading,
  catalogError,
  deletingFactId,
  onAdd,
  onEdit,
  onRemove,
  onRemoveUnsupported,
  onQueryChange,
  onReloadCatalog,
}: ClinicalDetailsSectionProps) {
  return (
    <section className="clinical-details-panel" aria-labelledby="clinical-details-heading">
      <div className="clinical-details-heading">
        <h2 id="clinical-details-heading">Clinical details</h2>
        <button
          className="primary-button"
          disabled={catalogLoading || Boolean(catalogError)}
          type="button"
          onClick={onAdd}
        >
          {catalogLoading ? 'Loading details…' : 'Add clinical detail'}
        </button>
      </div>
      {catalogError ? (
        <div className="form-error clinical-catalog-error" role="alert">
          <span>{catalogError}</span>
          <button className="text-button" type="button" onClick={onReloadCatalog}>Try again</button>
        </div>
      ) : null}
      <label className="clinical-detail-search">
        <span className="visually-hidden">Search current details</span>
        <input
          aria-label="Search current details"
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search by clinical label or value"
        />
      </label>
      <div className="clinical-detail-groups">
        {(Object.keys(clinicalGroupLabels) as PatientFactGroup[]).map((group) => (
          <section className="clinical-detail-group" key={group}>
            <header><h3>{clinicalGroupLabels[group]}</h3><span>{groupedFacts[group].length}</span></header>
            {groupedFacts[group].length === 0 ? (
              <div className="clinical-group-empty">
                {query ? 'No matching details in this group.' : 'No current details.'}
              </div>
            ) : (
              <div className="clinical-detail-rows">
                {groupedFacts[group].map((fact) => {
                  const entry = factCatalogEntry(catalog, fact)
                  return (
                    <article className="clinical-detail-row" key={fact.id}>
                      <div className="clinical-detail-primary">
                        <strong>{entry?.display_label ?? factLabel(fact)}</strong>
                        <span>{clinicalValueLabel(fact, entry)}</span>
                      </div>
                      <div className="clinical-detail-meta">
                        {fact.effective_date ? <span>{fact.effective_date}</span> : null}
                      </div>
                      <div className="record-actions">
                        {entry ? (
                          <button className="text-button" type="button" onClick={() => onEdit(fact)}>Edit</button>
                        ) : (
                          <span className="unsupported-detail">Review only</span>
                        )}
                        <button
                          className="text-button danger"
                          disabled={deletingFactId === fact.id}
                          onClick={() => onRemove(fact)}
                          type="button"
                        >
                          {deletingFactId === fact.id ? 'Removing…' : 'Remove'}
                        </button>
                      </div>
                    </article>
                  )
                })}
              </div>
            )}
          </section>
        ))}
        {patient.unsupported_details.length > 0 ? (
          <section className="clinical-detail-group unsupported-detail-group">
            <header><h3>Other details</h3><span>{patient.unsupported_details.length}</span></header>
            <p className="unsupported-detail-guidance">
              These entries are saved for review and are not used for screening.
            </p>
            <div className="clinical-detail-rows">
              {patient.unsupported_details.map((detail) => (
                <article className="clinical-detail-row unsupported-detail-row" key={detail.id}>
                  <div className="clinical-detail-primary"><strong>{detail.label}</strong><span>{detail.category}</span></div>
                  <div className="clinical-detail-meta">{detail.context ? <span>{detail.context}</span> : null}</div>
                  <div className="record-actions">
                    <span className="unsupported-detail">Review only</span>
                    <button
                      className="text-button danger"
                      disabled={deletingFactId === detail.id}
                      onClick={() => onRemoveUnsupported(detail)}
                      type="button"
                    >
                      {deletingFactId === detail.id ? 'Removing…' : 'Remove'}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </section>
  )
}
