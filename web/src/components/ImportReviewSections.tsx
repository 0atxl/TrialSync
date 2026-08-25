import { FileText } from 'lucide-react'

import { type ImportDocument } from '../api/client'

export function ImportedSource({ review, onContinue }: { review: ImportDocument; onContinue: () => void }) {
  return (
    <section aria-labelledby="imported-source-title">
      <div className="ingestion-stage-heading">
        <h2 id="imported-source-title">Imported source</h2>
      </div>
      <div className="import-source-summary">
        <FileText aria-hidden="true" size={21} />
        <span>
          <strong>{review.filename ?? 'Pasted text'}</strong>
          <small>{review.quality.page_count} page{Number(review.quality.page_count) === 1 ? '' : 's'}</small>
        </span>
      </div>
      <div className="imported-source-pages">
        {review.pages.map((page) => (
          <section key={page.page}><span>Page {page.page}</span><pre>{page.text}</pre></section>
        ))}
      </div>
      <div className="form-actions ingestion-actions">
        <button className="primary-button" type="button" onClick={onContinue}>Continue</button>
      </div>
    </section>
  )
}

export function SourceShortcut({ review, onOpen }: { review: ImportDocument; onOpen: () => void }) {
  return (
    <button className="source-shortcut" type="button" onClick={onOpen}>
      <FileText aria-hidden="true" size={17} />
      <span><strong>View source</strong><small>{review.filename ?? 'Pasted text'}</small></span>
    </button>
  )
}

function ImportSummary({ review, unresolved }: { review: ImportDocument; unresolved: number }) {
  const selected = review.kind === 'patient'
    ? (review.candidates.facts ?? []).filter((item) => item.selected).length
    : (review.candidates.criteria ?? []).filter((item) => item.selected).length
  return (
    <div className="ingestion-review">
      <section>
        <h3>{review.kind === 'patient'
          ? review.candidates.profile.display_name
          : review.candidates.profile.title}</h3>
        <p>{review.kind === 'patient'
          ? 'Patient profile reviewed'
          : review.candidates.profile.condition}</p>
      </section>
      <section>
        <h3>{review.kind === 'patient' ? 'Clinical details' : 'Trial criteria'}</h3>
        <p>{selected} selected{unresolved ? ` · ${unresolved} need review` : ''}</p>
      </section>
    </div>
  )
}

export function StepActions({ back, next, nextLabel }: {
  back: () => void
  next: () => void
  nextLabel: string
}) {
  return (
    <div className="form-actions ingestion-actions">
      <button className="secondary-button" type="button" onClick={back}>Back</button>
      <button className="primary-button" type="button" onClick={next}>{nextLabel}</button>
    </div>
  )
}

export function FinalImportReview({ review, unresolved, error, saving, onDiscard, onSave, onApprove }: {
  review: ImportDocument
  unresolved: number
  error: string
  saving: boolean
  onDiscard: () => void
  onSave: () => void
  onApprove: () => void
}) {
  return (
    <section aria-labelledby="import-final-review-title">
      <div className="ingestion-stage-heading">
        <h2 id="import-final-review-title">Check before creating the {review.kind}</h2>
      </div>
      <ImportSummary review={review} unresolved={unresolved} />
      {review.warnings.length ? (
        <details className="import-review-notes">
          <summary>{review.warnings.length} review note{review.warnings.length === 1 ? '' : 's'}</summary>
          <ul>{review.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
        </details>
      ) : null}
      {error ? <div className="form-error" role="alert">{error}</div> : null}
      <div className="review-actions streamlined">
        <button
          className="danger-button danger-button-subtle"
          disabled={saving}
          type="button"
          onClick={onDiscard}
        >
          Discard import
        </button>
        <div>
          <button className="secondary-button" disabled={saving} type="button" onClick={onSave}>
            Save for later
          </button>
          <button
            className="primary-button"
            disabled={saving || unresolved > 0 || review.status !== 'needs_review'}
            type="button"
            onClick={onApprove}
          >
            {saving ? 'Saving…' : `Create ${review.kind}`}
          </button>
        </div>
      </div>
    </section>
  )
}
