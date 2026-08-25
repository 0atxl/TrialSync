import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { apiRequest, type Patient, type Trial } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { approvedVersions } from './screeningHelpers'

export function NewScreeningPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const requestedPatientId = searchParams.get('patient_id') ?? ''
  const [patients, setPatients] = useState<Patient[]>([])
  const [trials, setTrials] = useState<Trial[]>([])
  const [patientId, setPatientId] = useState('')
  const [versionId, setVersionId] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [loadedPatients, loadedTrials] = await Promise.all([
        apiRequest<Patient[]>('/patients', {}, token),
        apiRequest<Trial[]>('/trials', {}, token),
      ])
      setPatients(loadedPatients)
      setTrials(loadedTrials)
      setPatientId(
        loadedPatients.some((patient) => patient.id === requestedPatientId)
          ? requestedPatientId
          : loadedPatients[0]?.id ?? '',
      )
      setVersionId(approvedVersions(loadedTrials)[0]?.version.id ?? '')
    } catch {
      setError('Screening inputs could not be loaded.')
    }
  }, [requestedPatientId, token])

  useEffect(() => { void load() }, [load])
  const versions = approvedVersions(trials)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!patientId || !versionId) {
      setError('Select a patient and trial.')
      return
    }
    setSaving(true)
    try {
      const result = await apiRequest<{ id: string }>('/screenings', {
        method: 'POST',
        body: JSON.stringify({ patient_id: patientId, trial_version_id: versionId }),
      }, token)
      navigate(`/screenings/${result.id}`)
    } catch {
      setError('The screening could not be run. Review the selected inputs and try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="route-entry workspace-page narrow-page">
      <Link className="back-link" to="/screenings">← Screenings</Link>
      <header className="page-heading"><h1>New screening</h1></header>
      <form className="screening-form" onSubmit={submit}>
        <label>
          Patient
          <select
            value={patientId}
            onChange={(event) => setPatientId(event.target.value)}
            required
          >
            <option value="">Select a patient</option>
            {patients.map((patient) => (
              <option value={patient.id} key={patient.id}>{patient.display_name}</option>
            ))}
          </select>
        </label>
        <label>
          Trial
          <select
            value={versionId}
            onChange={(event) => setVersionId(event.target.value)}
            required
          >
            <option value="">Select a trial</option>
            {versions.map(({ trial, version }) => (
              <option value={version.id} key={version.id}>{trial.title}</option>
            ))}
          </select>
        </label>
        {!patients.length || !versions.length ? (
          <div className="empty-state">
            <p>
              Add at least one patient and one trial with criteria.{' '}
              <Link to="/patients">Open patients</Link> or{' '}
              <Link to="/trials">open trials</Link>.
            </p>
          </div>
        ) : null}
        {error ? <div className="form-error" role="alert">{error}</div> : null}
        <button
          className="primary-button"
          disabled={saving || !patients.length || !versions.length}
          type="submit"
        >
          {saving ? 'Running screening…' : 'Run screening'}
        </button>
      </form>
    </section>
  )
}
