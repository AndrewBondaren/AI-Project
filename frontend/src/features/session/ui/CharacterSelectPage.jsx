import { useNavigate, useParams } from 'react-router-dom'
import { useCharacters } from '../hooks/useCharacters'
import { createSession } from '../service'
import styles from './CharacterSelectPage.module.css'
import { useState } from 'react'

export default function CharacterSelectPage() {
  const { worldId } = useParams()
  const { characters, loading, importing, error, importCharacter } = useCharacters(worldId)
  const [starting, setStarting] = useState(false)
  const navigate = useNavigate()

  const handleSelect = async (characterId) => {
    setStarting(true)
    try {
      const session = await createSession(worldId, characterId)
      navigate(`/chat/${session.id}`)
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
        <p className={styles.hint}>Нет персонажей для этого мира. Импортируй из файла.</p>
      )}

      <ul className={styles.list}>
        {characters.map(c => (
          <li
            key={c.character_uid}
            className={`${styles.card} ${starting ? styles.disabled : ''}`}
            onClick={() => !starting && handleSelect(c.character_uid)}
          >
            <span className={styles.cardName}>{c.display_name}</span>
            {(c.display_class || c.display_gender) && (
              <span className={styles.cardMeta}>
                {[c.display_class, c.display_gender].filter(Boolean).join(' · ')}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
