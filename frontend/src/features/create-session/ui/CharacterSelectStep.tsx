import type { CharacterSummary } from '@/shared/types/records'
import { errorMessage } from '@/shared/lib/errorMessage'
import { useNavigate, useParams } from 'react-router-dom'
import { createSession } from '../api/createSession'
import { copyCharacter } from '@/entities/character/api/characterApi'
import { useSessions } from '@/entities/session/model/useSessions'
import { useState } from 'react'
import ImportCard from '@/shared/ui/ImportCard'
import Icon from '@/shared/ui/Icon'
import RequestError from '@/shared/ui/RequestError'

interface CharacterSelectProps {
  characters: CharacterSummary[]
  loading: boolean
  importing: boolean
  deleting: boolean
  error: string | null
  actionError: string | null
  onRetry: () => void
  onImport: () => void
  onDelete: (character: CharacterSummary) => void
}

export default function CharacterSelectStep({ characters, loading, importing, deleting, error, actionError, onImport, onDelete, onRetry }: CharacterSelectProps) {
  const { worldId } = useParams()
  const { refresh: refreshSessions } = useSessions()
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const navigate = useNavigate()
  const busy = starting || importing || deleting || loading

  const handleSelect = async (character: CharacterSummary) => {
    if (!worldId) return
    const session = character.activeSession
    const inOtherWorld = session && session.worldId !== worldId

    if (inOtherWorld) {
      const ok = window.confirm(
        `"${character.name}" уже в сессии с миром "${session.worldName}".\n\nБудет создана копия персонажа для этого мира. Продолжить?`
      )
      if (!ok) return
    }

    setStarting(true)
    setStartError(null)
    try {
      const characterId = inOtherWorld
        ? (await copyCharacter(character.id)).id
        : character.id
      const s = await createSession(worldId, characterId)
      await refreshSessions()
      navigate(`/chat/${s.id}`)
    } catch (e) {
      setStartError(errorMessage(e))
      setStarting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-wrap items-center gap-4 pr-8 max-sm:items-start">
        <button className="text-xs text-muted transition-colors hover:text-foreground" onClick={() => navigate('/new')}>← Назад</button>
        <h1 className="text-xl font-semibold max-sm:text-[17px]">Выбери персонажа</h1>
      </div>

      {loading && <p role="status" className="text-muted italic">Загрузка персонажей…</p>}
      {error && <RequestError message={error} onRetry={onRetry} />}
      {actionError && <RequestError message={actionError} />}
      {startError && <RequestError message={startError} />}

      {!loading && !error && characters.length === 0 && (
        <p className="text-muted italic">Нет персонажей. Импортируй из файла.</p>
      )}

      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ImportCard label="Импортировать персонажа" importing={importing} disabled={busy} onImport={onImport} />
        {characters.map(c => {
          const session = c.activeSession
          const sameWorld = session?.worldId === worldId
          return (
            <li
              key={c.id}
              className="relative"
            >
              <button type="button" disabled={busy} onClick={() => handleSelect(c)} className="flex h-full min-h-32 w-full flex-col items-start gap-3 rounded-lg border border-line bg-panel p-4 pr-12 text-left transition-colors enabled:hover:border-line-hover enabled:hover:bg-raised disabled:opacity-50">
                <span className="flex w-full flex-wrap items-center gap-3">
                  <Icon name="alien" size={32} />
                  <span className="flex-1 text-base font-semibold wrap-anywhere">{c.name}</span>
                  {session && (
                    <span className={`rounded px-2 py-0.5 text-xs ${sameWorld ? 'bg-accent/15 text-accent' : 'border border-line bg-raised text-muted'}`}>
                      {sameWorld ? 'В сессии' : `В сессии: ${session.worldName}`}
                    </span>
                  )}
                </span>
                {(c.characterClass || c.gender) && (
                  <span className="text-xs text-muted">
                    {[c.characterClass, c.gender].filter(Boolean).join(' · ')}
                  </span>
                )}
              </button>
              <button
                type="button"
                className="absolute top-3 right-3 rounded-md p-1.5 enabled:hover:bg-danger/10 disabled:opacity-40"
                aria-label={`Удалить персонажа «${c.name}»`}
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
