import { createBrowserRouter } from 'react-router-dom'

import { ProtectedRoute } from '../auth/ProtectedRoute'
import { AppLayout } from '../components/AppLayout'
import { AuthPage } from '../pages/AuthPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { PatientDetailPage } from '../pages/PatientDetailPage'
import { PatientsPage } from '../pages/PatientsPage'
import { NewPatientPage } from '../pages/NewPatientPage'
import { TrialDetailPage } from '../pages/TrialDetailPage'
import { TrialsPage } from '../pages/TrialsPage'
import { NewTrialPage } from '../pages/NewTrialPage'
import { ImportReviewPage } from '../pages/ImportReviewPage'
import { NewImportPage } from '../pages/NewImportPage'
import { BatchDetailPage } from '../pages/BatchDetailPage'
import { BatchScreeningPage } from '../pages/BatchScreeningPage'
import { DashboardPage } from '../pages/DashboardPage'
import { HelpPage } from '../pages/HelpPage'
import { NewScreeningPage } from '../pages/NewScreeningPage'
import { ScreeningDetailPage } from '../pages/ScreeningDetailPage'
import { ScreeningHistoryPage } from '../pages/ScreeningHistoryPage'
import { RouteErrorPage } from '../pages/RouteErrorPage'
import { CatalogManagementPage } from '../pages/CatalogManagementPage'

export const routes = [
  { path: '/login', element: <AuthPage mode="login" />, errorElement: <RouteErrorPage /> },
  { path: '/register', element: <AuthPage mode="register" />, errorElement: <RouteErrorPage /> },
  {
    element: <ProtectedRoute />,
    errorElement: <RouteErrorPage />,
    children: [
      {
        path: '/',
        element: <AppLayout />,
        errorElement: <RouteErrorPage />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: 'patients', element: <PatientsPage /> },
          { path: 'patients/new', element: <NewPatientPage /> },
          { path: 'patients/:patientId', element: <PatientDetailPage /> },
          { path: 'trials', element: <TrialsPage /> },
          { path: 'trials/new', element: <NewTrialPage /> },
          { path: 'trials/:trialId', element: <TrialDetailPage /> },
          { path: 'imports/new', element: <NewImportPage /> },
          { path: 'imports/:importId', element: <ImportReviewPage /> },
          { path: 'screenings', element: <ScreeningHistoryPage /> },
          { path: 'screenings/new', element: <NewScreeningPage /> },
          { path: 'screenings/:screeningId', element: <ScreeningDetailPage /> },
          { path: 'batches/new', element: <BatchScreeningPage /> },
          { path: 'batches/:batchId', element: <BatchDetailPage /> },
          { path: 'catalog', element: <CatalogManagementPage /> },
          { path: 'help', element: <HelpPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
