import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { ApiError, apiRequest, type ImportDocument } from '../api/client'
import { useAuth } from '../auth/AuthContext'

const errorMessages: Record<string, string> = {
  IMPORT_EMPTY: 'The selected source is empty.',
  IMPORT_TOO_LARGE: 'The selected source exceeds the import size limit.',
  IMPORT_WRONG_TYPE: 'Choose a valid PDF file.',
  PDF_MALFORMED: 'This PDF is malformed and could not be read.',
  PDF_ENCRYPTED: 'Encrypted PDFs are not supported.',
  PDF_EMPTY: 'This PDF does not contain any pages.',
  PDF_OCR_NOT_ENABLED: 'No machine-readable text was found. Upload a text-based PDF; OCR is not enabled.',
}

const readBase64 = (file: File) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader()
  reader.addEventListener('load', () => resolve(String(reader.result).split(',')[1] ?? ''))
  reader.addEventListener('error', () => reject(reader.error))
  reader.readAsDataURL(file)
})

export function NewImportPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const kind = params.get('kind') === 'trial' ? 'trial' : 'patient'
  const [sourceType, setSourceType] = useState<'text' | 'pdf'>('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const back = kind === 'patient' ? '/patients' : '/trials'

  const selectFile = (selectedFile: File | null) => {
    setFile(selectedFile)
    setError(selectedFile && selectedFile.size > 5_000_000
      ? 'The selected source exceeds the 5 MB PDF limit.'
      : '')
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (sourceType === 'pdf' && !file) { setError('Choose a text-based PDF to continue.'); return }
    if (file && file.size > 5_000_000) { setError('The selected source exceeds the 5 MB PDF limit.'); return }
    setLoading(true)
    setError('')
    try {
      const body = sourceType === 'text'
        ? { kind, source_type: 'text', text }
        : { kind, source_type: 'pdf', content_base64: await readBase64(file as File), filename: file?.name, mime_type: file?.type || 'application/pdf' }
      const review = await apiRequest<ImportDocument>('/imports', { method: 'POST', body: JSON.stringify(body) }, token)
      navigate(`/imports/${review.id}`)
    } catch (exception) {
      setError(exception instanceof ApiError ? errorMessages[exception.code] ?? exception.message : 'The source could not be analyzed.')
    } finally { setLoading(false) }
  }

  return <section className="route-entry workspace-page form-page"><Link className="back-link" to={back}>← {kind === 'patient' ? 'Patients' : 'Trials'}</Link><header className="page-heading"><div><p className="eyebrow">Review-first import</p><h1>Import a synthetic {kind}</h1><p>Paste synthetic source text or upload a text-based PDF. Extracted candidates remain unapproved until you review them.</p></div></header><form className="creation-form import-form" onSubmit={submit}><div className="form-section"><fieldset className="source-toggle"><legend>Source type</legend><label><input type="radio" name="source_type" checked={sourceType === 'text'} onChange={() => setSourceType('text')} /> Paste text</label><label><input type="radio" name="source_type" checked={sourceType === 'pdf'} onChange={() => setSourceType('pdf')} /> Upload PDF</label></fieldset>{sourceType === 'text' ? <label>Synthetic source text<textarea required rows={14} value={text} onChange={(event) => setText(event.target.value)} placeholder={kind === 'patient' ? 'Patient name: Synthetic Ada\nDate of birth: 1985-05-14\nHbA1c: 8.2 %' : 'Title: Synthetic protocol\nInclusion Criteria:\n- Age 18 to 75 years'} /></label> : <label>Text-based PDF<input accept="application/pdf,.pdf" required type="file" onChange={(event) => selectFile(event.target.files?.[0] ?? null)} /><small>Maximum 5 MB. Scanned images require OCR and are rejected in this phase.</small></label>}</div><div className="data-boundary"><strong>Synthetic data only</strong><span>Source text is treated as untrusted candidate input.</span></div>{error && <div className="form-error" role="alert">{error}</div>}<div className="form-actions"><Link className="secondary-button" to={back}>Cancel</Link><button className="primary-button" disabled={loading} type="submit">{loading ? 'Analyzing…' : 'Analyze for review'}</button></div></form></section>
}
