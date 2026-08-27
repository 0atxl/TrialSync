import { useEffect, useRef, useState } from 'react'
import {
  Beaker,
  ChevronDown,
  CircleHelp,
  ClipboardCheck,
  LayoutDashboard,
  LogOut,
  Microscope,
  PanelLeftClose,
  PanelLeftOpen,
  Settings2,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { ThemeToggle } from './ThemeToggle'

const SIDEBAR_KEY = 'trialsync_sidebar_collapsed'

type NavItem = {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}

const navItems: NavItem[] = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/patients', label: 'Patients', icon: Users },
  { to: '/trials', label: 'Trials', icon: ClipboardCheck },
  { to: '/screenings', label: 'Screenings', icon: Beaker },
  { to: '/research', label: 'Research', icon: Microscope },
  { to: '/help', label: 'Help', icon: CircleHelp },
]

function initialSidebarState() {
  try { return localStorage.getItem(SIDEBAR_KEY) === 'true' }
  catch { return false }
}

function initials(name: string | undefined) {
  return (name ?? 'TrialSync')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(initialSidebarState)
  const accountMenuRef = useRef<HTMLDetailsElement>(null)

  useEffect(() => {
    function closeOnOutsidePointer(event: PointerEvent) {
      if (event.target instanceof Node && !accountMenuRef.current?.contains(event.target)) {
        accountMenuRef.current?.removeAttribute('open')
      }
    }
    document.addEventListener('pointerdown', closeOnOutsidePointer)
    return () => document.removeEventListener('pointerdown', closeOnOutsidePointer)
  }, [])

  const closeAccountMenu = () => accountMenuRef.current?.removeAttribute('open')

  const toggleSidebar = () => setCollapsed((current) => {
    const next = !current
    try { localStorage.setItem(SIDEBAR_KEY, String(next)) } catch { /* optional preference */ }
    return next
  })

  return (
    <div className={`app-shell${collapsed ? ' sidebar-collapsed' : ''}`}>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="topbar">
        <Link className="brand" to="/" aria-label="TrialSync overview">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          <strong>TrialSync</strong>
        </Link>

        <div className="topbar-actions">
          <ThemeToggle />
          <details className="account-menu" ref={accountMenuRef}>
          <summary aria-label={`${user?.display_name ?? 'User'} account menu`}>
            <span className="account-avatar" aria-hidden="true">{initials(user?.display_name)}</span>
            <span className="account-name">{user?.display_name}</span>
            <ChevronDown aria-hidden="true" size={15} strokeWidth={2} />
          </summary>
          <div className="account-popover">
            <div className="account-identity">
              <strong>{user?.display_name}</strong>
              <span>{user?.email}</span>
            </div>
            {user?.is_catalog_admin ? (
              <NavLink to="/administration/catalog" onClick={closeAccountMenu}>
                <Settings2 aria-hidden="true" size={16} />
                Catalog administration
              </NavLink>
            ) : null}
            <button type="button" onClick={() => { closeAccountMenu(); logout() }}>
              <LogOut aria-hidden="true" size={16} />
              Sign out
            </button>
          </div>
          </details>
        </div>
      </header>

      <div className="shell-grid">
        <aside className="sidebar" aria-label="Primary navigation">
          <button
            className="sidebar-collapse-button"
            type="button"
            onClick={toggleSidebar}
            aria-expanded={!collapsed}
            aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          >
            {collapsed
              ? <PanelLeftOpen aria-hidden="true" size={18} />
              : <PanelLeftClose aria-hidden="true" size={18} />}
          </button>
          <div className="sidebar-main">
            <nav>
              {navItems.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    aria-label={item.label}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
                  >
                    <Icon aria-hidden="true" size={19} strokeWidth={1.9} />
                    <span className="nav-label">{item.label}</span>
                  </NavLink>
                )
              })}
            </nav>
          </div>
        </aside>

        <main className="page" id="main-content" tabIndex={-1}><Outlet /></main>
      </div>
    </div>
  )
}
