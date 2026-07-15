import { createBrowserRouter } from 'react-router-dom'

import { ProtectedRoute } from '../auth/ProtectedRoute'
import { AppLayout } from '../components/AppLayout'
import { AuthPage } from '../pages/AuthPage'
import { FoundationPage } from '../pages/FoundationPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { PatientDetailPage } from '../pages/PatientDetailPage'
import { PatientsPage } from '../pages/PatientsPage'
import { PlaceholderPage } from '../pages/PlaceholderPage'
import { TrialDetailPage } from '../pages/TrialDetailPage'
import { TrialsPage } from '../pages/TrialsPage'

export const routes = [
  { path: '/login', element: <AuthPage mode="login" /> },
  { path: '/register', element: <AuthPage mode="register" /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: '/',
        element: <AppLayout />,
        children: [
          { index: true, element: <FoundationPage /> },
          { path: 'patients', element: <PatientsPage /> },
          { path: 'patients/:patientId', element: <PatientDetailPage /> },
          { path: 'trials', element: <TrialsPage /> },
          { path: 'trials/:trialId', element: <TrialDetailPage /> },
          {
            path: 'screenings',
            element: (
              <PlaceholderPage
                eyebrow="Evidence review"
                title="Screenings"
                description="Deterministic screening begins in Phase 3."
              />
            ),
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
