import { Navigate, useSearchParams } from 'react-router-dom'

export function NewImportPage() {
  const [params] = useSearchParams()
  const kind = params.get('kind') === 'trial' ? 'trial' : 'patient'
  return <Navigate replace to={`/${kind === 'patient' ? 'patients' : 'trials'}/new?source=import`} />
}
