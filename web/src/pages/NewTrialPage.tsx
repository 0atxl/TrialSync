import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { apiRequest, type Trial } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function NewTrialPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    setSaving(true)
    try {
      const trial = await apiRequest<Trial>('/trials', { method: 'POST', body: JSON.stringify({ title: values.get('title'), condition: values.get('condition'), phase: values.get('phase') || null }) }, token)
      navigate(`/trials/${trial.id}`)
    } catch { setError('The trial could not be created.') }
    finally { setSaving(false) }
  }
  return <section className="route-entry workspace-page form-page"><Link className="back-link" to="/trials">← Trials</Link><header className="page-heading"><div><p className="eyebrow">New protocol</p><h1>Add a trial</h1><p>TrialSync generates a registry reference. Create a draft version and criteria after saving.</p></div></header><form className="creation-form" onSubmit={submit}><div className="form-section"><h2>Protocol profile</h2><div className="form-grid"><label>Trial title<input name="title" required autoFocus /></label><label>Condition<input name="condition" required /></label><label>Phase<input name="phase" placeholder="Optional" /></label></div></div>{error && <div className="form-error" role="alert">{error}</div>}<div className="form-actions"><Link className="secondary-button" to="/trials">Cancel</Link><button className="primary-button" disabled={saving} type="submit">{saving ? 'Creating…' : 'Create trial'}</button></div></form></section>
}
