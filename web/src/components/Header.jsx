import { NavLink } from 'react-router-dom'

export default function Header() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <NavLink to="/" className="logo">
          Datacenter Testimonies
        </NavLink>
        <p className="tagline">
          Resident voices on crypto mining & data centers in New York State
        </p>
        <nav className="main-nav">
          <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} end>
            Map
          </NavLink>
          <NavLink to="/testimonies" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            Testimonies
          </NavLink>
          <NavLink to="/add" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            Add testimony
          </NavLink>
        </nav>
      </div>
    </header>
  )
}
