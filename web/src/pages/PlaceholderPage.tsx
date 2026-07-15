interface PlaceholderPageProps {
  eyebrow: string
  title: string
  description: string
}

export function PlaceholderPage({ eyebrow, title, description }: PlaceholderPageProps) {
  return (
    <section className="placeholder-page route-entry">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p className="lede">{description}</p>
      <div className="placeholder-boundary">
        <span>Planned</span>
        <p>This route is established, but no domain behavior is implemented in Phase 1.</p>
      </div>
    </section>
  )
}

