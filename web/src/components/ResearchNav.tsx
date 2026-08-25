import { NavLink } from 'react-router-dom'

export function ResearchNav() {
  return <nav className="research-subnav" aria-label="Research workspace">
    <NavLink to="/research/dropout" className={({ isActive }) => isActive ? 'active' : ''}>Dropout</NavLink>
    <NavLink to="/research/cohorts" className={({ isActive }) => isActive ? 'active' : ''}>Cohorts</NavLink>
  </nav>
}
