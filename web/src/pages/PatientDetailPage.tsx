import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiRequest, type Patient } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function PatientDetailPage() {
  const { patientId = '' } = useParams()
  const { token } = useAuth()
  const [patient, setPatient] = useState<Patient | null>(null)
  const [error, setError] = useState('')
  const [factType, setFactType] = useState('condition')
  const [concept, setConcept] = useState('')
  const [value, setValue] = useState('')
  const [unit, setUnit] = useState('')

  const load = useCallback(async () => {
    try {
      setPatient(await apiRequest<Patient>(`/patients/${patientId}`, {}, token))
      setError('')
    } catch {
      setError('Patient record could not be loaded.')
    }
  }, [patientId, token])

  useEffect(() => {
    void load()
  }, [load])

  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    try {
      await apiRequest(
        `/patients/${patientId}`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            display_name: values.get('display_name'),
            date_of_birth: values.get('date_of_birth') || null,
            sex: values.get('sex') || null,
          }),
        },
        token,
      )
      await load()
    } catch {
      setError('Patient profile could not be updated.')
    }
  }

  const addFact = async (event: FormEvent) => {
    event.preventDefault()
    const numeric = value.trim() === '' ? undefined : Number(value)
    try {
      await apiRequest(
        `/patients/${patientId}/facts`,
        {
          method: 'POST',
          body: JSON.stringify({
            fact_type: factType,
            concept,
            value_numeric: Number.isNaN(numeric) ? undefined : numeric,
            value_text: Number.isNaN(numeric) ? value : undefined,
            unit: numeric === undefined ? undefined : unit || undefined,
          }),
        },
        token,
      )
      setConcept('')
      setValue('')
      setUnit('')
      await load()
    } catch {
      setError('Fact could not be saved. Numeric values require a unit.')
    }
  }

  const deleteFact = async (factId: string) => {
    try {
      await apiRequest(`/patients/${patientId}/facts/${factId}`, { method: 'DELETE' }, token)
      await load()
    } catch {
      setError('Fact could not be removed.')
    }
  }

  if (error && !patient) return <div className="form-error" role="alert">{error}</div>
  if (!patient) return <div className="loading-state">Loading patient record…</div>

  return (
    <section className="route-entry workspace-page">
      <Link className="back-link" to="/patients">← Patients</Link>
      <header className="page-heading">
        <p className="eyebrow">{patient.external_id}</p>
        <h1>{patient.display_name}</h1>
      </header>
      <form className="profile-form" onSubmit={saveProfile}>
        <label>Display name<input name="display_name" required defaultValue={patient.display_name} /></label>
        <label>Date of birth<input name="date_of_birth" type="date" defaultValue={patient.date_of_birth ?? ''} /></label>
        <label>Sex when relevant<input name="sex" defaultValue={patient.sex ?? ''} /></label>
        <button className="secondary-button" type="submit">Save profile</button>
      </form>
      <form className="fact-form" onSubmit={addFact}>
        <label>Fact type<select value={factType} onChange={(event) => setFactType(event.target.value)}><option value="condition">Condition</option><option value="medication">Medication</option><option value="observation">Lab / observation</option><option value="demographic">Demographic</option></select></label>
        <label>Concept<input required value={concept} onChange={(event) => setConcept(event.target.value)} placeholder="HbA1c or Type 2 diabetes" /></label>
        <label>Value<input value={value} onChange={(event) => setValue(event.target.value)} /></label>
        <label>Unit<input value={unit} onChange={(event) => setUnit(event.target.value)} placeholder="%, mg/dL…" /></label>
        <button className="primary-button" type="submit">Add fact</button>
      </form>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="record-list">
        {patient.facts.length === 0 ? (
          <div className="empty-state"><h2>No structured facts</h2><p>Add conditions, medications, observations, or demographics.</p></div>
        ) : patient.facts.map((fact) => (
          <article className="record-row" key={fact.id}>
            <div><span className="record-kind">{fact.fact_type}</span><strong>{fact.concept}</strong><p>{fact.value_numeric ?? fact.value_text ?? fact.assertion} {fact.unit}</p></div>
            <div className="record-actions"><small>{fact.source_label}</small><button className="text-button danger" onClick={() => void deleteFact(fact.id)} type="button">Remove</button></div>
          </article>
        ))}
      </div>
    </section>
  )
}
