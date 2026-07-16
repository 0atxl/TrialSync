import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { apiRequest, type Patient } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function PatientsPage() {
  const { token } = useAuth()
  const [patients, setPatients] = useState<Patient[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    setLoading(true)
    try { setPatients(await apiRequest('/patients', {}, token)); setError('') }
    catch { setError('Patients could not be loaded.') }
    finally { setLoading(false) }
  }, [token])
  useEffect(() => { void load() }, [load])
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    return term ? patients.filter((patient) => `${patient.display_name} ${patient.external_id}`.toLowerCase().includes(term)) : patients
  }, [patients, query])

  return <section className="route-entry workspace-page">
    <header className="page-heading"><div><p className="eyebrow">Structured records</p><h1>Patients</h1><p>Records with explicit facts, units, dates, and provenance.</p></div><div className="page-actions"><Link className="secondary-button" to="/imports/new?kind=patient">Import text or PDF</Link><Link className="primary-button" to="/patients/new">Add patient</Link></div></header>
    <div className="list-toolbar"><label className="search-field"><span>Search patients</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Type a name or record ID" /></label><span>{filtered.length} of {patients.length} records</span></div>
    {error ? <div className="form-error" role="alert">{error}</div> : loading ? <div className="loading-state">Loading patient records…</div> : filtered.length === 0 ? <div className="empty-state"><h2>{patients.length ? 'No matching patients' : 'No patients yet'}</h2><p>{patients.length ? 'Try a different name or record ID.' : 'Add a patient to begin structured entry.'}</p></div> : <div className="record-table"><div className="record-table-head" aria-hidden="true"><span>Patient</span><span>Profile</span><span>Facts</span><span /></div>{filtered.map((patient) => <article className="record-table-row" key={patient.id}><div><strong>{patient.display_name}</strong><small>{patient.external_id}</small></div><span>{patient.sex || 'Not specified'}{patient.date_of_birth ? ` · born ${patient.date_of_birth}` : ''}</span><span className="tabular">{patient.facts.length}</span><Link to={`/patients/${patient.id}`}>Review record</Link></article>)}</div>}
  </section>
}
