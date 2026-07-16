import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { apiRequest, type Patient, type Trial } from '../api/client'
import { useAuth } from '../auth/AuthContext'

const PATIENT_LIMIT = 50
const TRIAL_LIMIT = 10
const PAIR_LIMIT = 500

export function BatchScreeningPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [patients, setPatients] = useState<Patient[]>([])
  const [trials, setTrials] = useState<Trial[]>([])
  const [patientIds, setPatientIds] = useState<string[]>([])
  const [versionIds, setVersionIds] = useState<string[]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [records, protocols] = await Promise.all([
        apiRequest<Patient[]>('/patients', {}, token),
        apiRequest<Trial[]>('/trials', {}, token),
      ])
      setPatients(records)
      setTrials(protocols)
      setError('')
    } catch {
      setError('Batch screening inputs could not be loaded.')
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const pairCount = patientIds.length * versionIds.length
  const blocked = !patientIds.length || !versionIds.length
    || patientIds.length > PATIENT_LIMIT || versionIds.length > TRIAL_LIMIT
    || pairCount > PAIR_LIMIT
  const toggle = (id: string, selected: string[], setSelected: (items: string[]) => void) => {
    setSelected(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id])
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (blocked) {
      setError('Select at least one patient and approved trial version within the configured limits.')
      return
    }
    setSaving(true)
    try {
      const batch = await apiRequest<{ id: string }>('/screening-batches', {
        method: 'POST',
        body: JSON.stringify({ patient_ids: patientIds, trial_version_ids: versionIds }),
      }, token)
      navigate(`/batches/${batch.id}`)
    } catch {
      setError('The batch could not be created. No partial results were saved.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="route-entry workspace-page">
      <Link className="back-link" to="/screenings">← Screening history</Link>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Bounded batch</p>
          <h1>Compare patients across protocols</h1>
          <p>TrialSync captures one immutable snapshot per selected patient, then runs the same deterministic single-screening operation for every pair.</p>
        </div>
      </header>
      <form onSubmit={submit}>
        <div className="batch-picker">
          <fieldset>
            <legend>Patients</legend>
            {patients.length ? patients.map((patient) => (
              <label className="check-row" key={patient.id}>
                <input type="checkbox" checked={patientIds.includes(patient.id)} onChange={() => toggle(patient.id, patientIds, setPatientIds)} />
                <span><strong>{patient.display_name}</strong><small>{patient.external_id} · {patient.facts.length} structured fact{patient.facts.length === 1 ? '' : 's'}</small></span>
              </label>
            )) : <div className="empty-state"><p>Add a patient before running a batch.</p></div>}
          </fieldset>
          <fieldset>
            <legend>Trial versions</legend>
            {trials.length ? trials.flatMap((trial) => {
              const approved = trial.versions.filter((version) => version.status === 'approved')
              if (!approved.length) return [(
                <label className="check-row check-row-disabled" key={trial.id}>
                  <input type="checkbox" disabled />
                  <span><strong>{trial.title}</strong><small>{trial.registry_id} · approve a version to enable screening</small></span>
                </label>
              )]
              return approved.map((version) => (
                <label className="check-row" key={version.id}>
                  <input type="checkbox" checked={versionIds.includes(version.id)} onChange={() => toggle(version.id, versionIds, setVersionIds)} />
                  <span><strong>{trial.title}</strong><small>{trial.registry_id} · approved version {version.version}</small></span>
                </label>
              ))
            }) : <div className="empty-state"><p>Add a trial and approve a version before running a batch.</p></div>}
          </fieldset>
        </div>
        <p className="batch-guidance">All current patients are shown. Trials without an approved version remain visible but unavailable because deterministic screening requires an immutable approved protocol.</p>
        <div className={`pair-preview ${pairCount > PAIR_LIMIT ? 'pair-warning' : ''}`}>
          <strong>{pairCount} screening pair{pairCount === 1 ? '' : 's'}</strong>
          <span>Limit: {PATIENT_LIMIT} patients × {TRIAL_LIMIT} versions, up to {PAIR_LIMIT} pairs.</span>
        </div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="primary-button" disabled={blocked || saving} type="submit">{saving ? 'Running batch…' : 'Run batch screening'}</button>
      </form>
    </section>
  )
}
