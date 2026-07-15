import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { apiRequest, type Patient } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function PatientsPage() {
  const { token } = useAuth()
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [externalId, setExternalId] = useState('')
  const [displayName, setDisplayName] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try { setPatients(await apiRequest<Patient[]>('/patients', {}, token)); setError('') }
    catch { setError('Patients could not be loaded.'); }
    finally { setLoading(false) }
  }, [token])
  useEffect(() => { void load() }, [load])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await apiRequest('/patients', { method: 'POST', body: JSON.stringify({ external_id: externalId, display_name: displayName }) }, token)
      setExternalId(''); setDisplayName(''); await load()
    } catch { setError('The synthetic patient could not be saved.') }
  }

  return (
    <section className="route-entry workspace-page">
      <header className="page-heading"><div><p className="eyebrow">Structured records</p><h1>Patients</h1><p>Fictional records only. Add facts on the patient detail page.</p></div></header>
      <form className="inline-form" onSubmit={submit}>
        <label>Synthetic ID<input required value={externalId} onChange={(event) => setExternalId(event.target.value)} placeholder="SYN-001" /></label>
        <label>Display name<input required value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Synthetic case A" /></label>
        <button className="primary-button" type="submit">Add patient</button>
      </form>
      {error && <div className="form-error" role="alert">{error}</div>}
      {loading ? <div className="loading-state">Loading patient records…</div> : patients.length === 0 ? <div className="empty-state"><h2>No patients yet</h2><p>Add a fictional patient above to begin structured entry.</p></div> : (
        <div className="data-table" role="table"><div className="data-row data-header" role="row"><span>Synthetic ID</span><span>Name</span><span>Facts</span><span /></div>{patients.map((patient) => <div className="data-row" role="row" key={patient.id}><strong>{patient.external_id}</strong><span>{patient.display_name}</span><span>{patient.facts.length}</span><Link to={`/patients/${patient.id}`}>Review</Link></div>)}</div>
      )}
    </section>
  )
}
