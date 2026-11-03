import { useNavigate, useParams } from 'react-router-dom'
import { createSession } from '../api/createSession'
import { copyCharacter } from '@/entities/character/api/characterApi'
import { useSessions } from '@/entities/session/model/useSessions'
import { useState } from 'react'

export default function CharacterSelectStep({ characters, loading, importing, error, onImport }) {
  const { worldId } = useParams()
  const { refresh: refreshSessions } = useSessions()
  const [starting, setStarting] = useState(false)
  const navigate = useNavigate()

  const handleSelect = async (character) => {
    const session = character.active_session
    const inOtherWorld = session && session.world_uid !== worldId

    if (inOtherWorld) {
      const ok = window.confirm(
        `"${character.display_name}" уже в сессии с миром "${session.world_name}".\n\nБудет создана копия персонажа для этого мира. Продолжить?`
      )
      if (!ok) return
    }

    setStarting(true)
    try {
      const characterId = inOtherWorld
        ? (await copyCharacter(character.character_uid)).character_uid
        : character.character_uid
      const s = await createSession(worldId, characterId)
      await refreshSessions()
      navigate(`/chat/${s.id}`)
    } catch (e) {
      alert(`Ошибка: ${e.message}`)
      setStarting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-wrap items-center gap-4 pr-8 max-sm:items-start">
        <button className="text-xs text-muted transition-colors hover:text-foreground" onClick={() => navigate('/new')}>← Назад</button>
        <h1 className="text-xl font-semibold max-sm:text-[17px]">Выбери персонажа</h1>
        <button
          className="rounded-lg border border-line bg-raised px-4 py-2 text-xs text-muted transition-colors enabled:hover:border-line-hover enabled:hover:text-foreground disabled:opacity-50"
          onClick={onImport}
          disabled={importing || starting}
        >
          {importing ? 'Импорт...' : 'Импортировать из файла'}
        </button>
      </div>

      {(loading || importing) && <p className="text-muted italic">Загрузка...</p>}
      {error && <p className="text-danger">Ошибка: {error}</p>}

      {!loading && !error && characters.length === 0 && (
        <p className="text-muted italic">Нет персонажей. Импортируй из файла.</p>
      )}

      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {characters.map(c => {
          const session = c.active_session
          const sameWorld = session?.world_uid === worldId
          return (
            <li
              key={c.character_uid}
              className={`flex min-h-32 cursor-pointer flex-col items-start gap-3 rounded-lg border border-line bg-panel p-4 transition-colors hover:border-line-hover hover:bg-raised ${starting ? "pointer-events-none opacity-50" : ''}`}
              tabIndex={starting ? -1 : 0}
              role="button"
              aria-disabled={starting}
              onKeyDown={e => { if (!starting && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); handleSelect(c) } }}
              onClick={() => !starting && handleSelect(c)}
            >
              <div className="flex w-full flex-wrap items-center gap-3">
                <img src="/icons/alien.svg" alt="" width="32" height="32" />
                <span className="flex-1 text-base font-semibold wrap-anywhere">{c.display_name}</span>
                {session && (
                  <span className={`rounded px-2 py-0.5 text-xs ${sameWorld ? "bg-accent/15 text-accent" : "border border-line bg-raised text-muted"}`}>
                    {sameWorld ? 'В сессии' : `В сессии: ${session.world_name}`}
                  </span>
                )}
              </div>
              {(c.display_class || c.display_gender) && (
                <span className="text-xs text-muted">
                  {[c.display_class, c.display_gender].filter(Boolean).join(' · ')}
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
