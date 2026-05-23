import { useNavigate } from 'react-router-dom'
import { useWorlds } from '../hooks/useWorlds'
import styles from './WorldSelectPage.module.css'

export default function WorldSelectPage() {
  const { worlds, loading, error } = useWorlds()
  const navigate = useNavigate()

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate('/')}>← Назад</button>
        <h1 className={styles.title}>Выбери мир</h1>
      </div>

      {loading && <p className={styles.hint}>Загрузка...</p>}
      {error   && <p className={styles.error}>Ошибка: {error}</p>}

      {!loading && !error && worlds.length === 0 && (
        <p className={styles.hint}>Нет доступных миров.</p>
      )}

      <ul className={styles.list}>
        {worlds.map(w => (
          <li
            key={w.world_uid}
            className={styles.card}
            onClick={() => navigate(`/new/${w.world_uid}`)}
          >
            <span className={styles.cardName}>{w.name}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
