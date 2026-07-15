import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Workspace', end: true },
  { to: '/patients', label: 'Patients' },
  { to: '/trials', label: 'Trials' },
  { to: '/screenings', label: 'Screenings' },
]

export function AppLayout() {
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
        <span className="phase-label">Foundation · Phase 1</span>
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

