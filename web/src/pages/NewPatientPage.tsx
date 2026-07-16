import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError, apiRequest, type Patient } from '../api/client'
import { useAuth } from '../auth/AuthContext'

type PatientValues = { display_name: string; date_of_birth: string; sex: string }

export function NewPatientPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [pending, setPending] = useState<PatientValues | null>(null)
  useEffect(() => {
    const dialog = dialogRef.current
    if (pending && dialog && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
    }
    if (!pending && dialog?.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [pending])

  const create = async (values: PatientValues, confirm = false) => {
    setSaving(true)
    try {
      const patient = await apiRequest<Patient>('/patients', { method: 'POST', body: JSON.stringify({ display_name: values.display_name, date_of_birth: values.date_of_birth || null, sex: values.sex || null, confirm_duplicate_name: confirm }) }, token)
      navigate(`/patients/${patient.id}`)
    } catch (exception) {
      if (exception instanceof ApiError && exception.code === 'PATIENT_NAME_REVIEW_REQUIRED') {
        setPending(values)
        setError('A patient with this name already exists. Review it or continue only if this is a distinct person.')
      } else setError('The patient could not be created.')
    } finally { setSaving(false) }
  }
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    void create({ display_name: String(data.get('display_name') ?? ''), date_of_birth: String(data.get('date_of_birth') ?? ''), sex: String(data.get('sex') ?? '') })
  }

  return <section className="route-entry workspace-page form-page"><Link className="back-link" to="/patients">← Patients</Link><header className="page-heading"><div><p className="eyebrow">New record</p><h1>Add a patient</h1><p>TrialSync generates a record ID. Add structured facts after saving the profile.</p></div></header><form className="creation-form" onSubmit={submit}><div className="form-section"><h2>Patient profile</h2><div className="form-grid"><label>Display name<input name="display_name" required autoFocus placeholder="Patient name" /></label><label>Date of birth<input name="date_of_birth" type="date" /></label><label>Sex when relevant<input name="sex" placeholder="Optional" /></label></div></div><div className="data-boundary"><strong>Data boundary</strong><span>Do not enter real patient information.</span></div>{error && !pending && <div className="form-error" role="alert">{error}</div>}<div className="form-actions"><Link className="secondary-button" to="/patients">Cancel</Link><button className="primary-button" disabled={saving} type="submit">{saving ? 'Creating…' : 'Create patient'}</button></div><dialog ref={dialogRef} className="confirmation-dialog" aria-labelledby="duplicate-patient-title" aria-describedby="duplicate-patient-copy" onCancel={() => { setPending(null); setError('') }}><p className="eyebrow">Possible duplicate</p><h2 id="duplicate-patient-title">Review this patient name</h2><p id="duplicate-patient-copy">{error}</p><div className="warning-actions"><Link className="secondary-button" to="/patients">Review existing records</Link><button autoFocus className="primary-button" disabled={saving} type="button" onClick={() => pending && void create(pending, true)}>{saving ? 'Creating…' : 'Create distinct patient'}</button></div></dialog></form></section>
}
