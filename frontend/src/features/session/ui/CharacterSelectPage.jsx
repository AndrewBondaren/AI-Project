import { useNavigate, useParams } from 'react-router-dom'
import { useCharacters } from '../hooks/useCharacters'
import { createSession, copyCharacter } from '../service'
import styles from './CharacterSelectPage.module.css'
import { useState } from 'react'

export default function CharacterSelectPage() {
  const { worldId } = useParams()
  const { characters, loading, importing, error, importCharacter } = useCharacters()
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
      navigate(`/chat/${s.id}`)
    } catch (e) {
      alert(`Ошибка: ${e.message}`)
      setStarting(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate('/new')}>← Назад</button>
        <h1 className={styles.title}>Выбери персонажа</h1>
        <button
          className={styles.importBtn}
          onClick={importCharacter}
          disabled={importing}
        >
          {importing ? 'Импорт...' : 'Импортировать из файла'}
        </button>
      </div>

      {(loading || importing) && <p className={styles.hint}>Загрузка...</p>}
      {error && <p className={styles.error}>Ошибка: {error}</p>}

      {!loading && !error && characters.length === 0 && (
        <p className={styles.hint}>Нет персонажей. Импортируй из файла.</p>
      )}

      <ul className={styles.list}>
        {characters.map(c => {
          const session = c.active_session
          const sameWorld = session?.world_uid === worldId
          return (
            <li
              key={c.character_uid}
              className={`${styles.card} ${starting ? styles.disabled : ''}`}
              onClick={() => !starting && handleSelect(c)}
            >
              <div className={styles.cardRow}>
                <span className={styles.cardName}>{c.display_name}</span>
                {session && (
                  <span className={`${styles.sessionBadge} ${sameWorld ? styles.sessionSame : styles.sessionOther}`}>
                    {sameWorld ? 'В сессии' : `В сессии: ${session.world_name}`}
                  </span>
                )}
              </div>
              {(c.display_class || c.display_gender) && (
                <span className={styles.cardMeta}>
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
