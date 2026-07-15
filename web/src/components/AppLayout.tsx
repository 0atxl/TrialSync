import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const navItems = [
  { to: '/', label: 'Workspace', end: true },
  { to: '/patients', label: 'Patients' },
  { to: '/trials', label: 'Trials' },
  { to: '/screenings', label: 'Screenings' },
  { to: '/batches/new', label: 'Batch screening' },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink className="brand" to="/" aria-label="TrialSync workspace">
          <span className="brand-mark" aria-hidden="true">
            TS
          </span>
          <span>
            <strong>TrialSync</strong>
            <small>Research workspace</small>
          </span>
        </NavLink>
        <div className="account-area"><span className="phase-label">{user?.display_name}</span><button className="text-button" onClick={logout}>Sign out</button></div>
      </header>

      <div className="shell-grid">
        <aside className="sidebar" aria-label="Primary navigation">
          <nav>
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="scope-note">
            <span className="scope-rule" aria-hidden="true" />
            <p>Synthetic data only</p>
            <small>Educational pre-screening prototype—not clinical guidance.</small>
          </div>
        </aside>

        <main className="page" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
