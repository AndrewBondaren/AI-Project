import styles from './MessageList.module.css'

const ROLE_LABEL = { user: 'Вы', bot: 'Мастер', system: 'Система' }

export default function MessageList({ messages }) {
  if (messages.length === 0) {
    return <p className={styles.empty}>Начни игру — отправь первое сообщение.</p>
  }

  return (
    <ul className={styles.list}>
      {messages.map((msg, i) => (
        <li key={i} className={`${styles.message} ${styles[msg.role]}`}>
          <span className={styles.role}>{ROLE_LABEL[msg.role] ?? msg.role}</span>
          <pre className={styles.text}>{msg.text}</pre>
        </li>
      ))}
    </ul>
  )
}
