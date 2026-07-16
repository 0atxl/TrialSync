import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { token, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (token) return <Navigate to="/" replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (mode === 'register') await register(email, displayName, password)
      else await login(email, password)
      const state = location.state as { from?: string } | null
      navigate(state?.from ?? '/', { replace: true })
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to reach TrialSync.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel route-entry">
        <div className="auth-intro">
          <span className="brand-mark">TS</span>
          <p className="eyebrow">Synthetic research workspace</p>
          <h1>Evidence starts with structured records.</h1>
          <p>Create and review fictional patient facts and trial criteria before screening.</p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          <div>
            <p className="eyebrow">{mode === 'login' ? 'Welcome back' : 'Create account'}</p>
            <h2>{mode === 'login' ? 'Sign in' : 'Register'}</h2>
          </div>
          {error && <div className="form-error" role="alert">{error}</div>}
          {mode === 'register' && (
            <label>Display name<input required minLength={2} value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
          )}
          <label>Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label>Password<input required minLength={mode === 'register' ? 10 : 1} type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {mode === 'login' && import.meta.env.DEV && (
            <button
              className="sample-data-button"
              type="button"
              onClick={() => {
                setEmail('demo@trialsync.example')
                setPassword('SyntheticDemo123!')
              }}
            >
              Use seeded synthetic demo
              <small>Fills local development credentials</small>
            </button>
          )}
          <button className="primary-button" disabled={busy} type="submit">{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
          <p className="auth-switch">
            {mode === 'login' ? 'Need a demo account?' : 'Already registered?'}{' '}
            <Link to={mode === 'login' ? '/register' : '/login'}>{mode === 'login' ? 'Register' : 'Sign in'}</Link>
          </p>
        </form>
      </section>
    </main>
  )
}
