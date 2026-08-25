import { ArrowRight, Eye, EyeOff } from 'lucide-react'
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

  const isLogin = mode === 'login'

  return (
    <main className="auth-page">
      <section className="auth-panel route-entry" aria-labelledby="auth-title">
        <div className="auth-intro">
          <div className="auth-brand">
            <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
            <strong>TrialSync</strong>
          </div>
          <div>
            <p>Patient–trial screening workspace</p>
            <span aria-hidden="true" />
          </div>
        </div>

        <form className="auth-form" onSubmit={submit}>
          <header>
            <h1 id="auth-title">{isLogin ? 'Sign in' : 'Create account'}</h1>
          </header>

          {error && <div className="form-error" role="alert">{error}</div>}

          {mode === 'register' && (
            <label>
              Display name
              <input
                required
                autoComplete="name"
                minLength={2}
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
          )}

          <label>
            Email
            <input
              required
              autoComplete="email"
              inputMode="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>

          <div className="auth-field">
            <label htmlFor="auth-password">Password</label>
            <div className="password-field">
              <input
                id="auth-password"
                required
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                minLength={isLogin ? 1 : 10}
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                aria-controls="auth-password"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showPassword}
                className="password-toggle"
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
              >
                {showPassword
                  ? <EyeOff aria-hidden="true" size={17} />
                  : <Eye aria-hidden="true" size={17} />}
              </button>
            </div>
          </div>

          {isLogin && (
            <button
              className="sample-data-button"
              type="button"
              onClick={() => {
                setEmail('demo@trialsync.example')
                setPassword('SyntheticDemo123!')
              }}
            >
              Fill saved login
            </button>
          )}

          <button className="primary-button auth-submit" disabled={busy} type="submit">
            {busy ? 'Please wait…' : isLogin ? 'Sign in' : 'Create account'}
            {!busy && <ArrowRight aria-hidden="true" size={17} />}
          </button>

          <p className="auth-switch">
            {isLogin ? 'New to TrialSync?' : 'Already have an account?'}{' '}
            <Link to={isLogin ? '/register' : '/login'}>{isLogin ? 'Create account' : 'Sign in'}</Link>
          </p>
        </form>
      </section>
    </main>
  )
}
