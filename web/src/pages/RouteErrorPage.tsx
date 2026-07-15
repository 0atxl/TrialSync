import { Link, isRouteErrorResponse, useRouteError } from 'react-router-dom'

export function RouteErrorPage() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error)
    ? error.statusText || 'The requested workspace page could not be opened.'
    : 'This page encountered an unexpected problem.'

  return (
    <main className="auth-page">
      <section className="configuration-error" role="alert">
        <p className="eyebrow">Workspace error</p>
        <h1>We could not display this page.</h1>
        <p>{message} Return to the workspace and try again.</p>
        <Link className="primary-button" to="/">Back to workspace</Link>
      </section>
    </main>
  )
}
