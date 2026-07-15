import { createBrowserRouter } from 'react-router-dom'

import { AppLayout } from '../components/AppLayout'
import { FoundationPage } from '../pages/FoundationPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { PlaceholderPage } from '../pages/PlaceholderPage'

export const routes = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <FoundationPage /> },
      {
        path: 'patients',
        element: (
          <PlaceholderPage
            eyebrow="Structured records"
            title="Patients"
            description="Synthetic patient entry and review will arrive in Phase 2."
          />
        ),
      },
      {
        path: 'trials',
        element: (
          <PlaceholderPage
            eyebrow="Protocol workspace"
            title="Trials"
            description="Trial versions and ordered criteria will arrive in Phase 2."
          />
        ),
      },
      {
        path: 'screenings',
        element: (
          <PlaceholderPage
            eyebrow="Evidence review"
            title="Screenings"
            description="Deterministic screening begins after structured records and rules are complete."
          />
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)

