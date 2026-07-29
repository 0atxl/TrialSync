import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FocusEvent,
  type HTMLAttributes,
  type ReactNode,
} from 'react'

export type ToastVariant = 'success' | 'information' | 'warning' | 'error'

type ToastAction = {
  label: string
  onClick: () => void
}

export type ToastInput = {
  variant: ToastVariant
  title?: string
  message: string
  action?: ToastAction
  durationMs?: number | null
  announce?: boolean
}

type ToastItem = ToastInput & {
  id: string
  title: string
  durationMs: number | null
}

type ToastContextValue = {
  showToast: (toast: ToastInput) => string
  dismissToast: (id: string) => void
}

const DEFAULT_TITLES: Record<ToastVariant, string> = {
  success: 'Saved',
  information: 'Notice',
  warning: 'Review needed',
  error: 'Something went wrong',
}

const ToastContext = createContext<ToastContextValue | null>(null)

function defaultDuration(variant: ToastVariant) {
  if (variant === 'success' || variant === 'information') return 5000
  if (variant === 'warning') return 8000
  return 10000
}

function ToastCard({
  toast,
  dismiss,
}: {
  toast: ToastItem
  dismiss: (id: string) => void
}) {
  const [paused, setPaused] = useState(false)
  const remainingMs = useRef(toast.durationMs)
  const startedAt = useRef<number | null>(null)

  useEffect(() => {
    if (paused || remainingMs.current === null) return
    startedAt.current = Date.now()
    const timer = window.setTimeout(() => dismiss(toast.id), remainingMs.current)
    return () => {
      window.clearTimeout(timer)
      if (startedAt.current !== null && remainingMs.current !== null) {
        remainingMs.current = Math.max(
          0,
          remainingMs.current - (Date.now() - startedAt.current),
        )
      }
      startedAt.current = null
    }
  }, [dismiss, paused, toast.id])

  const leaveFocus = (event: FocusEvent<HTMLElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setPaused(false)
  }

  const liveRegionProps: Pick<HTMLAttributes<HTMLElement>, 'role' | 'aria-live'> =
    toast.announce === false
      ? { role: 'group', 'aria-live': 'off' }
      : { role: toast.variant === 'error' ? 'alert' : 'status' }

  return (
    <article
      className={`toast toast-${toast.variant}`}
      {...liveRegionProps}
      aria-atomic="true"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={leaveFocus}
    >
      <span className="toast-marker" aria-hidden="true" />
      <div className="toast-copy">
        <strong>{toast.title}</strong>
        <p>{toast.message}</p>
        {toast.action ? (
          <button
            className="toast-action"
            type="button"
            onClick={() => {
              toast.action?.onClick()
              dismiss(toast.id)
            }}
          >
            {toast.action.label}
          </button>
        ) : null}
      </div>
      <button
        className="toast-dismiss"
        type="button"
        aria-label={`Dismiss ${toast.title.toLowerCase()} notification`}
        onClick={() => dismiss(toast.id)}
      >
        <span aria-hidden="true">×</span>
      </button>
    </article>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(0)

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback((input: ToastInput) => {
    nextId.current += 1
    const id = `toast-${nextId.current}`
    setToasts((current) => [
      ...current,
      {
        ...input,
        id,
        title: input.title ?? DEFAULT_TITLES[input.variant],
        durationMs:
          input.durationMs === undefined ? defaultDuration(input.variant) : input.durationMs,
      },
    ])
    return id
  }, [])

  const value = useMemo(() => ({ showToast, dismissToast }), [dismissToast, showToast])
  const visible = toasts.slice(0, 3)

  return (
    <ToastContext.Provider value={value}>
      {children}
      <section className="toast-viewport" aria-label="Notifications">
        {visible.map((toast) => (
          <ToastCard key={toast.id} toast={toast} dismiss={dismissToast} />
        ))}
      </section>
    </ToastContext.Provider>
  )
}

// Context hooks intentionally share this module with their provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within ToastProvider')
  return context
}
