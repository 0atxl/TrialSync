import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="placeholder-page route-entry">
      <p className="eyebrow">404 · Not found</p>
      <h1>This workspace route does not exist.</h1>
      <p className="lede">Return to the foundation overview to continue.</p>
      <Link className="text-link" to="/">
        Back to workspace
      </Link>
    </section>
  )
}

