import { Link, NavLink } from 'react-router-dom'
import { useSessions } from '@/entities/session/model/useSessions'
import Icon from '@/shared/ui/Icon'

export default function AppSidebar() {
  const { sessions, loading, error } = useSessions()
  return (
    <aside id="app-sidebar" className="flex h-full w-72 shrink-0 flex-col border-r border-line bg-panel px-5 py-6 xl:w-90 xl:px-7 max-md:w-52 max-md:px-3 max-sm:w-44">
      <Link to="/" className="-mx-5 mb-6 flex items-center gap-2.5 border-b border-line px-5 pb-7 font-display text-2xl font-bold whitespace-nowrap xl:-mx-7 xl:px-7 xl:text-3xl max-md:mx-0 max-md:px-0 max-md:text-lg max-sm:text-sm">
        <Icon name="logo" className="max-sm:hidden" /><span>RPG Engine</span>
      </Link>
      <Link to="/new" className="flex items-center justify-center gap-2 rounded-lg border-2 border-line p-2.5 font-bold hover:bg-accent/7 max-md:text-xs"><Icon name="plus" size={18} /> Новая сессия</Link>
      <nav className="mt-6 min-h-0 flex-1 overflow-y-auto" aria-label="Кампании">
        <Link to="/" className="text-xs tracking-[1.8px] text-muted">КАМПАНИИ</Link>
        {loading && <p className="py-4 text-xs text-muted">Загрузка...</p>}
        {error && <p role="alert" className="py-4 text-xs text-danger">Не удалось загрузить кампании</p>}
        {!loading && !error && !sessions.length && <p className="py-4 text-xs text-muted">Ваши приключения появятся здесь</p>}
        <ul className="mt-3 flex flex-col gap-1.5">{sessions.map(s => (
          <li key={s.id}>
            <NavLink to={`/chat/${s.id}`} className={({ isActive }) => `flex items-start gap-2.5 rounded-lg border p-3 wrap-anywhere hover:border-line hover:bg-accent/7 max-md:px-1 max-md:text-xs ${isActive ? 'border-line bg-accent/7' : 'border-transparent'}`}>
              <Icon name="mapIcon" /><span><strong>{s.world_name ?? 'Мир удалён'}</strong><span className="mt-1 block text-xs text-muted">{s.character_name ?? 'Персонаж удалён'}</span></span>
            </NavLink>
          </li>
        ))}</ul>
      </nav>
      <div className="mt-6 border-t border-line pt-6">
        <NavLink to="/settings/backend" className="flex items-center gap-3 py-2.5 hover:text-white"><Icon name="setting" />Настройки</NavLink>
        <div className="flex items-center gap-3 py-2.5"><Icon name="user" />Путник</div>
      </div>
    </aside>
  )
}
