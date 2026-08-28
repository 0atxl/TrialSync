import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { apiRequest, type Patient } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Pagination } from '../components/Pagination'

const PAGE_SIZE = 10

export function PatientsPage() {
  const { token } = useAuth()
  const [patients, setPatients] = useState<Patient[]>([])
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setPatients(await apiRequest('/patients', {}, token))
      setError('')
    } catch {
      setError('Patients could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    return term
      ? patients.filter((patient) => patient.display_name.toLowerCase().includes(term))
      : patients
  }, [patients, query])

  useEffect(() => {
    setPage(1)
  }, [query])

  const paginated = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return filtered.slice(start, start + PAGE_SIZE)
  }, [filtered, page])

  return (
    <section className="route-entry workspace-page">
      <header className="page-heading">
        <h1>Patients</h1>
        <div className="page-actions">
          <Link className="primary-button" to="/patients/new">Add patient</Link>
        </div>
      </header>
      <div className="list-toolbar">
        <label className="search-field">
          <span>Search patients</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Patient name"
          />
        </label>
        <span>{filtered.length} of {patients.length}</span>
      </div>
      {error ? (
        <div className="form-error" role="alert">{error}</div>
      ) : loading ? (
        <div className="loading-state">Loading patients…</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <h2>{patients.length ? 'No matching patients' : 'No patients yet'}</h2>
          <p>{patients.length ? 'Try another name.' : 'Add a patient to begin.'}</p>
        </div>
      ) : (
        <>
          <div className="record-table">
            <div className="record-table-head" aria-hidden="true">
              <span>Patient</span><span>Profile</span><span>Details</span><span />
            </div>
            {paginated.map((patient) => (
              <article className="record-table-row" key={patient.id}>
                <div><strong>{patient.display_name}</strong></div>
                <span>
                  {patient.sex || 'Not specified'}
                  {patient.date_of_birth ? ` · born ${patient.date_of_birth}` : ''}
                </span>
                <span className="tabular">{patient.facts.length}</span>
                <Link to={`/patients/${patient.id}`}>Open</Link>
              </article>
            ))}
          </div>
          <Pagination currentPage={page} totalItems={filtered.length} pageSize={PAGE_SIZE} onPageChange={setPage} />
        </>
      )}
    </section>
  )
}
