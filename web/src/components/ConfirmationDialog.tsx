import { useEffect, useRef, type ReactNode } from 'react'

type ConfirmationDialogProps = {
  open: boolean
  eyebrow?: string
  title: string
  children: ReactNode
  confirmLabel: string
  busyLabel: string
  busy?: boolean
  onCancel: () => void
  onConfirm: () => void
}

export function ConfirmationDialog({
  open,
  eyebrow,
  title,
  children,
  confirmLabel,
  busyLabel,
  busy = false,
  onCancel,
  onConfirm,
}: ConfirmationDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = `confirmation-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
    }
    if (!open && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [open])

  return (
    <dialog
      ref={dialogRef}
      className="confirmation-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => { event.preventDefault(); onCancel() }}
    >
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <h2 id={titleId}>{title}</h2>
      <div className="confirmation-copy">{children}</div>
      <div className="warning-actions">
        <button className="secondary-button" disabled={busy} type="button" onClick={onCancel}>Cancel</button>
        <button className="danger-button" disabled={busy} type="button" onClick={onConfirm}>
          {busy ? busyLabel : confirmLabel}
        </button>
      </div>
    </dialog>
  )
}
