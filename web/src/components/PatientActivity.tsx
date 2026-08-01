import type { PatientChangeEvent } from '../api/client'

function labelFromPayload(event: PatientChangeEvent) {
  const concept = event.after_json?.concept ?? event.before_json?.concept
  if (typeof concept !== 'string') return event.entity_type === 'patient' ? 'Patient profile' : 'Clinical detail'
  return concept
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function eventLabel(event: PatientChangeEvent) {
  const label = labelFromPayload(event)
  switch (event.event_type) {
    case 'patient_created': return 'Patient profile created'
    case 'profile_updated': return 'Demographics updated'
    case 'fact_created': return `${label} added`
    case 'fact_updated': return `${label} updated`
    case 'fact_voided': return `${label} removed`
    case 'fact_restored': return `${label} restored`
    default: return 'Patient record updated'
  }
}

export function PatientActivity({ events }: { events: PatientChangeEvent[] }) {
  return (
    <section className="patient-activity" aria-labelledby="patient-activity-heading">
      <div className="patient-activity-heading">
        <div>
          <p className="eyebrow">Record history</p>
          <h2 id="patient-activity-heading">Recent activity</h2>
        </div>
        <span>{events.length}</span>
      </div>
      {events.length === 0 ? (
        <p className="patient-activity-empty">No recorded changes yet.</p>
      ) : (
        <ol className="patient-activity-list">
          {events.map((event) => (
            <li key={event.id}>
              <div>
                <strong>{eventLabel(event)}</strong>
                {event.reason ? <p>Reason: {event.reason}</p> : null}
              </div>
              <time dateTime={event.created_at}>
                {new Date(event.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
              </time>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
