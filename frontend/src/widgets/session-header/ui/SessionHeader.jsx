import { useLocation } from 'react-router-dom'
import { useSessions } from '@/entities/session/model/useSessions'
import Icon from '@/shared/ui/Icon'

export default function SessionHeader({ sidebarOpen, onToggleSidebar }) {
  const { pathname } = useLocation()
  const { sessions } = useSessions()
  const session = sessions.find(s => pathname === `/chat/${s.id}`)
  const isChat = pathname.startsWith('/chat/')
  const title = isChat ? (session?.world_name ?? 'Приключение') : pathname.startsWith('/new') ? 'Новая сессия' : pathname.startsWith('/settings') ? 'Настройки' : 'Кампании'
  return (
    <header className="flex min-h-23 items-center gap-3 border-b border-line bg-panel px-7 py-5 max-md:px-4">
      <button className="flex shrink-0 rounded-lg border border-line bg-accent/7 p-1.5 hover:bg-accent/15" onClick={onToggleSidebar} aria-label={sidebarOpen ? 'Скрыть панель кампаний' : 'Показать панель кампаний'} aria-expanded={sidebarOpen} aria-controls="app-sidebar">
        <Icon name={sidebarOpen ? 'left' : 'mapIcon'} />
      </button>
      <h1 className="text-[22px] font-bold wrap-anywhere max-md:text-[17px]">{title}{isChat && session?.character_name && <span className="text-muted"> · {session.character_name}</span>}</h1>
    </header>
  )
}
