import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import { router } from './app/router'
import { AuthProvider } from './auth/AuthContext'
import { ToastProvider } from './components/ToastProvider'
import './styles.css'
import './styles/workflows.css'
import './styles/records.css'
import './styles/foundation.css'
import './styles/overview.css'
import './styles/ingestion.css'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('TrialSync root element was not found')
}

createRoot(rootElement).render(
  <StrictMode>
    <AuthProvider>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </AuthProvider>
  </StrictMode>,
)
