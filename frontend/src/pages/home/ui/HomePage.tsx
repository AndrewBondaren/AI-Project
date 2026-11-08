import type { MouseEvent } from 'react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessions } from '@/entities/session/model/useSessions'
import { errorMessage } from '@/shared/lib/errorMessage'
import RequestError from '@/shared/ui/RequestError'

export default function HomePage() {
  const { sessions, loading, error, refresh, deleteSession } = useSessions()
  const navigate = useNavigate()
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const handleDelete = async (e: MouseEvent<HTMLButtonElement>, id: string) => {
    e.stopPropagation()
    if (!window.confirm('Удалить сессию? Это действие нельзя отменить.')) return
    setDeletingId(id)
    setDeleteError(null)
    try {
      await deleteSession(id)
    } catch (error) {
      setDeleteError(errorMessage(error))
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

      {loading && <p role="status" className="text-muted italic">Загрузка сессий…</p>}
      {error && <RequestError message={error} onRetry={refresh} />}
      {deleteError && <RequestError message={deleteError} />}

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
            <span className={s.worldName ? "text-base font-semibold" : "text-sm text-danger italic"}>
              {s.worldName ?? 'Мир удалён'}
            </span>
            <span className={s.characterName ? "text-sm text-muted" : "text-sm text-danger italic"}>
              {s.characterName ?? 'Персонаж удалён'}
            </span>
            <div className="mt-1 flex items-center justify-between gap-2">
              <span className="text-xs text-faint">{formatDate(s.lastActiveAt)}</span>
              <button
                className="rounded border border-transparent px-2 py-1 text-xs text-faint enabled:hover:border-danger enabled:hover:bg-danger/10 enabled:hover:text-danger disabled:opacity-40"
                disabled={deletingId !== null || loading}
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

function formatDate(iso: string) {
  const date = new Date(iso)
  const now   = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / 86_400_000)
  const time = date.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })
  if (diffDays === 0) return `Сегодня в ${time}`
  if (diffDays === 1) return `Вчера в ${time}`
  return date.toLocaleDateString('ru', { day: 'numeric', month: 'long' })
}
