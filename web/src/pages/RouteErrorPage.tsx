import { Link, isRouteErrorResponse, useRouteError } from 'react-router-dom'

export function RouteErrorPage() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error)
    ? error.statusText || 'The requested workspace page could not be opened.'
    : 'This page encountered an unexpected problem.'

  return (
    <main className="auth-page">
      <section className="route-state route-state-error" role="alert">
        <span className="route-state-code">Error</span>
        <h1>We could not open this page</h1>
        <p>{message}</p>
        <Link className="primary-button" to="/">Return to Overview</Link>
      </section>
    </main>
  )
}
