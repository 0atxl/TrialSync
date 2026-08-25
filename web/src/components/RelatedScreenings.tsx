import { Link } from 'react-router-dom'

import type { Screening } from '../api/client'
import { stateLabel } from '../pages/screeningHelpers'

type RelatedScreeningsProps = {
  screenings: Screening[]
  counterpart: 'patient' | 'trial'
}

export function RelatedScreenings({ screenings, counterpart }: RelatedScreeningsProps) {
  return (
    <section className="record-secondary-section" aria-labelledby="related-screenings-heading">
      <div className="record-secondary-heading">
        <h2 id="related-screenings-heading">Saved screenings</h2>
        <span>{screenings.length}</span>
      </div>
      {screenings.length === 0 ? (
        <p className="record-secondary-empty">No saved screenings for this record.</p>
      ) : (
        <div className="related-screening-list">
          {screenings.slice(0, 6).map((screening) => (
            <article key={screening.id}>
              <div>
                <strong>
                  {counterpart === 'trial'
                    ? screening.trial_version.title
                    : screening.patient_snapshot.display_name}
                </strong>
                <time dateTime={screening.screening_date}>{screening.screening_date}</time>
              </div>
              <span className={`state state-${screening.overall_state}`}>
                {stateLabel(screening.overall_state)}
              </span>
              <Link to={`/screenings/${screening.id}`}>Review</Link>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
