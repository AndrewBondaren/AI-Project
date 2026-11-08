import type { WorldSummary } from '@/shared/types/records'
import { useNavigate } from 'react-router-dom'
import ImportCard from '@/shared/ui/ImportCard'
import RequestError from '@/shared/ui/RequestError'

interface WorldSelectProps {
  worlds: WorldSummary[]
  loading: boolean
  importing: boolean
  error: string | null
  actionError: string | null
  onRetry: () => void
  onImport: () => void
}

export default function WorldSelectStep({ worlds, loading, error, actionError, importing, onImport, onRetry }: WorldSelectProps) {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-wrap items-center gap-4 pr-8 max-sm:items-start">
        <button className="text-xs text-muted transition-colors hover:text-foreground" onClick={() => navigate('/')}>← Назад</button>
        <h1 className="text-xl font-semibold max-sm:text-[17px]">Выбери мир</h1>
      </div>

      {loading && <p role="status" className="text-muted italic">Загрузка миров…</p>}
      {error && <RequestError message={error} onRetry={onRetry} />}
      {actionError && <RequestError message={actionError} />}

      {!loading && !error && worlds.length === 0 && (
        <p className="text-muted italic">Нет доступных миров.</p>
      )}

      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ImportCard label="Импортировать мир" importing={importing} disabled={loading} onImport={onImport} />
        {worlds.map(w => (
          <li key={w.id}>
            <button type="button" disabled={importing} onClick={() => navigate(`/new/${w.id}`)} className="flex h-full min-h-32 w-full flex-col items-start gap-3 rounded-lg border border-line bg-panel p-4 text-left transition-colors enabled:hover:border-line-hover enabled:hover:bg-raised disabled:opacity-50">
              <img src="/icons/world.svg" alt="" width="32" height="32" />
              <span className="text-base font-semibold wrap-anywhere">{w.name}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
