import { useNavigate } from 'react-router-dom'
import { useWorlds } from '@/entities/world/model/useWorlds'

export default function WorldSelectStep() {
  const { worlds, loading, error } = useWorlds()
  const navigate = useNavigate()

  return (
    <div className="flex flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-wrap items-center gap-4 pr-8 max-sm:items-start">
        <button className="text-xs text-muted transition-colors hover:text-foreground" onClick={() => navigate('/')}>← Назад</button>
        <h1 className="text-xl font-semibold max-sm:text-[17px]">Выбери мир</h1>
      </div>

      {loading && <p className="text-muted italic">Загрузка...</p>}
      {error   && <p className="text-danger">Ошибка: {error}</p>}

      {!loading && !error && worlds.length === 0 && (
        <p className="text-muted italic">Нет доступных миров.</p>
      )}

      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {worlds.map(w => (
          <li
            key={w.world_uid}
            className="flex min-h-32 cursor-pointer flex-col items-start gap-3 rounded-lg border border-line bg-panel p-4 transition-colors hover:border-line-hover hover:bg-raised"
            tabIndex={0}
            role="button"
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/new/${w.world_uid}`) } }}
            onClick={() => navigate(`/new/${w.world_uid}`)}
          >
            <img src="/icons/world.svg" alt="" width="32" height="32" />
            <span className="flex-1 text-base font-semibold wrap-anywhere">{w.name}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
