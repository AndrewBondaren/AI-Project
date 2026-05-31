import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessions } from '../hooks/useSessions'
import styles from './SessionPage.module.css'

export default function SessionPage() {
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
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Сессии</h1>
        <button className={styles.newBtn} onClick={() => navigate('/new')}>
          Новая игра
        </button>
      </div>

      {loading && <p className={styles.hint}>Загрузка...</p>}
      {error   && <p className={styles.error}>Ошибка: {error}</p>}

      {!loading && !error && sessions.length === 0 && (
        <p className={styles.hint}>Нет сессий. Нажми «Новая игра» чтобы начать.</p>
      )}

      <ul className={styles.list}>
        {sessions.map(s => (
          <li
            key={s.id}
            className={styles.card}
            onClick={() => navigate(`/chat/${s.id}`)}
          >
            <span className={s.world_name ? styles.cardWorld : styles.cardDeleted}>
              {s.world_name ?? 'Мир удалён'}
            </span>
            <span className={s.character_name ? styles.cardCharacter : styles.cardDeleted}>
              {s.character_name ?? 'Персонаж удалён'}
            </span>
            <div className={styles.cardFooter}>
              <span className={styles.cardDate}>{formatDate(s.last_active_at)}</span>
              <button
                className={styles.deleteBtn}
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
