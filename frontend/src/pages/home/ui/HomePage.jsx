import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessions } from '@/entities/session/model/useSessions'

export default function HomePage() {
  const { sessions, loading, error, deleteSession } = useSessions()
  const navigate = useNavigate()
  const [deletingId, setDeletingId] = useState(null)

  const handleDelete = async (e, id) => {
    e.stopPropagation()
    if (!window.confirm('Удалить сессию? Это действие нельзя отменить.')) return
    setDeletingId(id)
    try {
      await deleteSession(id)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-semibold max-sm:text-[17px]">Сессии</h1>
        <button className="rounded-lg border border-line bg-accent/7 px-4 py-2 text-accent hover:bg-accent/15" onClick={() => navigate('/new')}>
          Новая игра
        </button>
      </div>

      {loading && <p className="text-muted italic">Загрузка...</p>}
      {error   && <p className="text-danger">Ошибка: {error}</p>}

      {!loading && !error && sessions.length === 0 && (
        <p className="text-muted italic">Нет сессий. Нажми «Новая игра» чтобы начать.</p>
      )}

      <ul className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,280px),1fr))] content-start gap-3">
        {sessions.map(s => (
          <li
            key={s.id}
            className="flex cursor-pointer flex-col gap-1 rounded-lg border border-line bg-panel p-4 transition-colors hover:border-line-hover hover:bg-raised"
            onClick={() => navigate(`/chat/${s.id}`)}
          >
            <span className={s.world_name ? "text-base font-semibold" : "text-sm text-danger italic"}>
              {s.world_name ?? 'Мир удалён'}
            </span>
            <span className={s.character_name ? "text-sm text-muted" : "text-sm text-danger italic"}>
              {s.character_name ?? 'Персонаж удалён'}
            </span>
            <div className="mt-1 flex items-center justify-between gap-2">
              <span className="text-xs text-faint">{formatDate(s.last_active_at)}</span>
              <button
                className="rounded border border-transparent px-2 py-1 text-xs text-faint enabled:hover:border-danger enabled:hover:bg-danger/10 enabled:hover:text-danger disabled:opacity-40"
                disabled={deletingId === s.id}
                onClick={e => handleDelete(e, s.id)}
              >
                {deletingId === s.id ? '...' : 'Удалить'}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function formatDate(iso) {
  const date = new Date(iso)
  const now   = new Date()
  const diffDays = Math.floor((now - date) / 86_400_000)
  const time = date.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })
  if (diffDays === 0) return `Сегодня в ${time}`
  if (diffDays === 1) return `Вчера в ${time}`
  return date.toLocaleDateString('ru', { day: 'numeric', month: 'long' })
}
