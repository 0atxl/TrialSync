import { AlertCircle, Inbox, LoaderCircle, type LucideIcon } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router-dom'

type PageHeaderProps = {
  title: string
  description?: string
  actions?: ReactNode
  back?: { label: string; to: string }
}

export function PageHeader({ title, description, actions, back }: PageHeaderProps) {
  return (
    <header className="compact-page-header">
      <div>
        {back ? <Link className="compact-back-link" to={back.to}>← {back.label}</Link> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  )
}

export function Toolbar({ label, children }: { label: string; children: ReactNode }) {
  return <div className="ui-toolbar" role="group" aria-label={label}>{children}</div>
}

type StateMessageProps = {
  state: 'loading' | 'empty' | 'error'
  title: string
  children?: ReactNode
  action?: ReactNode
}

const stateIcons: Record<StateMessageProps['state'], LucideIcon> = {
  loading: LoaderCircle,
  empty: Inbox,
  error: AlertCircle,
}

export function StateMessage({ state, title, children, action }: StateMessageProps) {
  const Icon = stateIcons[state]
  return (
    <section
      className={`ui-state ui-state-${state}`}
      role={state === 'error' ? 'alert' : 'status'}
      aria-live={state === 'loading' ? 'polite' : undefined}
    >
      <Icon className={state === 'loading' ? 'ui-state-spinner' : undefined} aria-hidden="true" size={20} />
      <div>
        <h2>{title}</h2>
        {children}
        {action ? <div className="ui-state-action">{action}</div> : null}
      </div>
    </section>
  )
}

export function TechnicalDetails({ children, label = 'Technical details' }: { children: ReactNode; label?: string }) {
  return <details className="technical-details"><summary>{label}</summary><div>{children}</div></details>
}

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string
  icon: LucideIcon
}

export function IconButton({ label, icon: Icon, className = '', ...props }: IconButtonProps) {
  return (
    <button className={`icon-button ${className}`.trim()} aria-label={label} title={label} {...props}>
      <Icon aria-hidden="true" size={18} />
    </button>
  )
}

type FieldProps = {
  label: string
  htmlFor: string
  hint?: string
  error?: string
  children: ReactNode
}

export function Field({ label, htmlFor, hint, error, children }: FieldProps) {
  const hintId = hint ? `${htmlFor}-hint` : undefined
  const errorId = error ? `${htmlFor}-error` : undefined
  return (
    <div className="ui-field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint ? <small id={hintId}>{hint}</small> : null}
      {error ? <span id={errorId} className="ui-field-error">{error}</span> : null}
    </div>
  )
}
