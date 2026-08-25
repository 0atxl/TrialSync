import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="route-state route-entry">
      <span className="route-state-code">404</span>
      <h1>Page not found</h1>
      <p>The address may be outdated or incorrect.</p>
      <Link className="primary-button" to="/">Return to Overview</Link>
    </section>
  )
}
