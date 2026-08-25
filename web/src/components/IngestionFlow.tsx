import { Check, FilePenLine, FileUp, UploadCloud } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'

import { ApiError, apiRequest, type ImportDocument } from '../api/client'
import { PageHeader } from './UiPrimitives'

export type IngestionSource = 'manual' | 'import'

type IngestionStep = {
  id: string
  label: string
}

export function IngestionPage({
  title,
  back,
  steps,
  currentStep,
  onStep,
  children,
}: {
  title: string
  back: { label: string; to: string }
  steps: IngestionStep[]
  currentStep: number
  onStep?: (step: number) => void
  children: ReactNode
}) {
  return (
    <section className="route-entry workspace-page ingestion-page">
      <PageHeader title={title} back={back} />
      <div className="ingestion-layout">
        <ol className="ingestion-steps" aria-label={`${title} progress`}>
          {steps.map((step, index) => {
            const complete = index < currentStep
            const active = index === currentStep
            return (
              <li className={active ? 'active' : complete ? 'complete' : ''} key={step.id}>
                <button
                  aria-current={active ? 'step' : undefined}
                  disabled={!onStep || index > currentStep}
                  type="button"
                  onClick={() => onStep?.(index)}
                >
                  <span>{complete ? <Check aria-hidden="true" size={15} /> : index + 1}</span>
                  {step.label}
                </button>
              </li>
            )
          })}
        </ol>
        <main className="ingestion-stage">{children}</main>
      </div>
    </section>
  )
}

export function SourceChoice({
  entity,
  onSelect,
}: {
  entity: 'patient' | 'trial'
  onSelect: (source: IngestionSource) => void
}) {
  return (
    <section className="ingestion-source" aria-labelledby="ingestion-source-title">
      <div className="ingestion-stage-heading">
        <h2 id="ingestion-source-title">How would you like to add this {entity}?</h2>
      </div>
      <div className="source-choice-grid">
        <button type="button" onClick={() => onSelect('manual')}>
          <FilePenLine aria-hidden="true" size={22} />
          <span><strong>Manual entry</strong><small>Enter and review the details yourself</small></span>
        </button>
        <button type="button" onClick={() => onSelect('import')}>
          <FileUp aria-hidden="true" size={22} />
          <span><strong>Import document</strong><small>Paste text or choose a PDF, then review</small></span>
        </button>
      </div>
    </section>
  )
}

const importErrors: Record<string, string> = {
  IMPORT_EMPTY: 'The selected source is empty.',
  IMPORT_TOO_LARGE: 'The selected source exceeds the import size limit.',
  IMPORT_WRONG_TYPE: 'Choose a valid PDF file.',
  PDF_MALFORMED: 'This PDF could not be read.',
  PDF_ENCRYPTED: 'Encrypted PDFs are not supported.',
  PDF_EMPTY: 'This PDF does not contain any pages.',
  PDF_TOO_MANY_PAGES: 'This PDF exceeds the 10-page limit.',
  OCR_UNAVAILABLE: 'Document scanning is unavailable. Use manual entry or paste text.',
  OCR_RENDER_FAILED: 'This PDF could not be prepared for reading.',
  OCR_FAILED: 'The document scan could not be read.',
  OCR_TIMEOUT: 'Reading this PDF took too long. Try a smaller file or paste text.',
  OCR_NO_TEXT: 'No readable text was found. Try a clearer scan or use manual entry.',
}

const readBase64 = (file: File) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader()
  reader.addEventListener('load', () => resolve(String(reader.result).split(',')[1] ?? ''))
  reader.addEventListener('error', () => reject(reader.error))
  reader.readAsDataURL(file)
})

export function DocumentImportStep({
  entity,
  token,
  onImported,
  onBack,
}: {
  entity: 'patient' | 'trial'
  token: string | null
  onImported: (review: ImportDocument) => void
  onBack: () => void
}) {
  const [mode, setMode] = useState<'text' | 'pdf'>('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const selectFile = (selected: File | null) => {
    setFile(selected)
    setError(selected && selected.size > 5_000_000 ? 'Choose a PDF smaller than 5 MB.' : '')
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (mode === 'text' && !text.trim()) { setError('Paste source text to continue.'); return }
    if (mode === 'pdf' && !file) { setError('Choose a PDF to continue.'); return }
    if (file && file.size > 5_000_000) { setError('Choose a PDF smaller than 5 MB.'); return }
    setLoading(true)
    setError('')
    try {
      const body = mode === 'text'
        ? { kind: entity, source_type: 'text', text }
        : {
            kind: entity,
            source_type: 'pdf',
            content_base64: await readBase64(file as File),
            filename: file?.name,
            mime_type: file?.type || 'application/pdf',
          }
      const review = await apiRequest<ImportDocument>(
        '/imports',
        { method: 'POST', body: JSON.stringify(body) },
        token,
      )
      onImported(review)
    } catch (exception) {
      setError(
        exception instanceof ApiError
          ? importErrors[exception.code] ?? exception.message
          : 'The source could not be analyzed.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section aria-labelledby="document-source-heading">
      <div className="ingestion-stage-heading">
        <h2 id="document-source-heading">Import {entity}</h2>
      </div>
      <form className="document-source-form" onSubmit={submit}>
        <div className="source-mode-switch" role="group" aria-label="Document source">
          <button aria-pressed={mode === 'text'} type="button" onClick={() => { setMode('text'); setError('') }}>Paste text</button>
          <button aria-pressed={mode === 'pdf'} type="button" onClick={() => { setMode('pdf'); setError('') }}>Choose PDF</button>
        </div>
        {mode === 'text' ? (
          <label>
            Source text
            <textarea
              autoFocus
              rows={12}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={entity === 'patient'
                ? 'Patient name, date of birth, conditions, medications, and results'
                : 'Trial title, condition, inclusion criteria, and exclusion criteria'}
            />
          </label>
        ) : (
          <label className="document-drop-field">
            <UploadCloud aria-hidden="true" size={24} />
            <strong>{file?.name ?? 'Choose a PDF'}</strong>
            <span>{file ? `${(file.size / 1_000_000).toFixed(1)} MB` : 'Up to 5 MB and 10 pages'}</span>
            <input
              accept="application/pdf,.pdf"
              aria-label="PDF document"
              type="file"
              onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
            />
          </label>
        )}
        {error ? <div className="form-error" role="alert">{error}</div> : null}
        <div className="form-actions ingestion-actions">
          <button className="secondary-button" disabled={loading} type="button" onClick={onBack}>Back</button>
          <button className="primary-button" disabled={loading} type="submit">{loading ? 'Reading document…' : 'Continue to review'}</button>
        </div>
      </form>
    </section>
  )
}
