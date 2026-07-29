import { ConfirmationDialog } from './ConfirmationDialog'
import type { UnsavedChangesControl } from '../hooks/useUnsavedChanges'

export function UnsavedChangesDialog({ control }: { control: UnsavedChangesControl }) {
  return (
    <ConfirmationDialog
      open={control.isBlocked}
      eyebrow="Unsaved changes"
      title="Discard unsaved changes?"
      confirmLabel="Discard changes"
      busyLabel="Discarding…"
      onCancel={control.stay}
      onConfirm={control.discardAndContinue}
    >
      <p>Your unsaved patient changes will be lost. Stay on this page to review or save them.</p>
    </ConfirmationDialog>
  )
}
