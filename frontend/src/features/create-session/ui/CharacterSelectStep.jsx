import { useNavigate, useParams } from 'react-router-dom'
import { createSession } from '../api/createSession'
import { copyCharacter } from '@/entities/character/api/characterApi'
import { useSessions } from '@/entities/session/model/useSessions'
import { useState } from 'react'
import ImportCard from '@/shared/ui/ImportCard'
import Icon from '@/shared/ui/Icon'

export default function CharacterSelectStep({ characters, loading, importing, deleting, error, onImport, onDelete }) {
  const { worldId } = useParams()
  const { refresh: refreshSessions } = useSessions()
  const [starting, setStarting] = useState(false)
  const navigate = useNavigate()
  const busy = starting || importing || deleting || loading

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
      </div>

      {loading && <p className="text-muted italic">Загрузка...</p>}
      {error && <p role="alert" className="text-danger">Ошибка: {error}</p>}

      {!loading && !error && characters.length === 0 && (
        <p className="text-muted italic">Нет персонажей. Импортируй из файла.</p>
      )}

      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ImportCard label="Импортировать персонажа" importing={importing} disabled={busy} onImport={onImport} />
        {characters.map(c => {
          const session = c.active_session
          const sameWorld = session?.world_uid === worldId
          return (
            <li
              key={c.character_uid}
              className="relative"
            >
              <button type="button" disabled={busy} onClick={() => handleSelect(c)} className="flex h-full min-h-32 w-full flex-col items-start gap-3 rounded-lg border border-line bg-panel p-4 pr-12 text-left transition-colors enabled:hover:border-line-hover enabled:hover:bg-raised disabled:opacity-50">
                <span className="flex w-full flex-wrap items-center gap-3">
                  <Icon name="alien" size={32} />
                  <span className="flex-1 text-base font-semibold wrap-anywhere">{c.display_name}</span>
                  {session && (
                    <span className={`rounded px-2 py-0.5 text-xs ${sameWorld ? 'bg-accent/15 text-accent' : 'border border-line bg-raised text-muted'}`}>
                      {sameWorld ? 'В сессии' : `В сессии: ${session.world_name}`}
                    </span>
                  )}
                </span>
                {(c.display_class || c.display_gender) && (
                  <span className="text-xs text-muted">
                    {[c.display_class, c.display_gender].filter(Boolean).join(' · ')}
                  </span>
                )}
              </button>
              <button
                type="button"
                className="absolute top-3 right-3 rounded-md p-1.5 enabled:hover:bg-danger/10 disabled:opacity-40"
                aria-label={`Удалить персонажа «${c.display_name}»`}
                title="Удалить персонажа"
                disabled={busy}
                onClick={() => onDelete(c)}
              >
                <Icon name="trash" size={18} />
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
