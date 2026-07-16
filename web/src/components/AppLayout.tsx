import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

const SIDEBAR_KEY = 'trialsync_sidebar_collapsed'
const navItems = [
  { to: '/', label: 'Workspace', glyph: 'W', end: true },
  { to: '/patients', label: 'Patients', glyph: 'P' },
  { to: '/trials', label: 'Trials', glyph: 'T' },
  { to: '/screenings', label: 'Screenings', glyph: 'S' },
  { to: '/batches/new', label: 'Batch screening', glyph: 'B' },
  { to: '/evaluation', label: 'Evaluation', glyph: 'E' },
]

function initialSidebarState() {
  try { return localStorage.getItem(SIDEBAR_KEY) === 'true' }
  catch { return false }
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(initialSidebarState)
  const toggleSidebar = () => setCollapsed((current) => {
    const next = !current
    try { localStorage.setItem(SIDEBAR_KEY, String(next)) } catch { /* optional preference */ }
    return next
  })

  return (
    <div className={`app-shell${collapsed ? ' sidebar-collapsed' : ''}`}>
      <header className="topbar">
        <NavLink className="brand" to="/" aria-label="TrialSync workspace">
          <span className="brand-mark" aria-hidden="true">TS</span>
          <span><strong>TrialSync</strong><small>Research workspace</small></span>
        </NavLink>
        <div className="account-area"><span className="phase-label">{user?.display_name}</span></div>
      </header>

      <div className="shell-grid">
        <aside className="sidebar" aria-label="Primary navigation">
          <div className="sidebar-main">
            <button
              className="sidebar-toggle"
              type="button"
              onClick={toggleSidebar}
              aria-expanded={!collapsed}
              aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
              title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            >
              <span aria-hidden="true">{collapsed ? '›' : '‹'}</span>
              <span className="nav-label">Collapse navigation</span>
            </button>
            <nav>
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  aria-label={item.label}
                  title={collapsed ? item.label : undefined}
                  className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
                >
                  <span className="nav-glyph" aria-hidden="true">{item.glyph}</span>
                  <span className="nav-label">{item.label}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="sidebar-footer">
            <div className="scope-note">
              <span className="scope-rule" aria-hidden="true" />
              <p>Synthetic data only</p>
              <small>Educational pre-screening prototype—not clinical guidance.</small>
            </div>
            <button className="signout-button" onClick={logout} title="Sign out">
              <span className="nav-glyph" aria-hidden="true">↗</span>
              <span className="nav-label">Sign out</span>
            </button>
          </div>
        </aside>

        <main className="page" id="main-content"><Outlet /></main>
      </div>
    </div>
  )
}
