import { NavLink, Outlet } from 'react-router-dom'
import styles from './AppLayout.module.css'

const NAV_ITEMS = [
  { to: '/',                 label: 'Сессии',    end: true },
  { to: '/settings/backend', label: 'Настройки', end: false },
]

export default function AppLayout() {
  return (
    <div className={styles.layout}>
      <nav className={styles.sidebar}>
        <div className={styles.logo}>RPG Engine</div>
        <ul className={styles.navList}>
          {NAV_ITEMS.map(({ to, label, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}
              >
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className={styles.content}>
        <Outlet />
      </main>
    </div>
  )
}
