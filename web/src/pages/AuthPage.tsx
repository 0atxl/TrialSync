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
  const [showPassword, setShowPassword] = useState(false)
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
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          <p className="eyebrow">Trial workspace</p>
          <h1>Evidence starts with structured records.</h1>
          <p>Create and review patient facts and trial criteria before screening.</p>
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
          {mode === 'login' ? (
            <div className="auth-field">
              <label htmlFor="login-password">Password</label>
              <div className="password-field">
                <input
                  id="login-password"
                  required
                  minLength={1}
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  aria-controls="login-password"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  className="password-toggle"
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>
          ) : (
            <label>Password<input required minLength={10} type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          )}
          {mode === 'login' && (
            <button
              className="sample-data-button"
              type="button"
              onClick={() => {
                setEmail('demo@trialsync.example')
                setPassword('SyntheticDemo123!')
              }}
            >
              Use demo account
              <small>Fills synthetic demonstration credentials</small>
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
