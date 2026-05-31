import { LocationSelectMessage, SceneReadyMessage } from './LocationSelectMessage'
import styles from './MessageList.module.css'

const ROLE_LABEL = { user: 'Вы', bot: 'Мастер', system: 'Система', pending: 'Вы (прервано)' }

function buildPendingText(statusLabel, thinkingMs, elapsed) {
  if (thinkingMs !== null) {
    const ms = thinkingMs > 0 ? thinkingMs : elapsed
    return `LLM думает... ${(ms / 1000).toFixed(1)}s`
  }
  if (!statusLabel) return `Обработка... ${(elapsed / 1000).toFixed(1)}s`
  const { phase, task_type: task = '' } = statusLabel
  const time = `${(elapsed / 1000).toFixed(1)}s`
  if (phase === 'repairing') return `Исправление: ${task}  ${time}`
  if (phase === 'executing') return `Выполнение: ${task}  ${time}`
  if (phase === 'done')      return `Готово: ${task}  ${time}`
  return `${phase}  ${time}`
}

function PendingMessage({ statusLabel, thinkingMs, elapsed }) {
  return (
    <li className={`${styles.message} ${styles.bot}`}>
      <span className={styles.role}>Мастер</span>
      <pre className={`${styles.text} ${styles.pendingText}`}>
        <span className={styles.dot} />
        {buildPendingText(statusLabel, thinkingMs, elapsed)}
      </pre>
    </li>
  )
}

function renderBotContent(msg, isActive, isStreaming, onSelect) {
  if (!msg.data) {
    return <pre className={styles.text}>{msg.text}</pre>
  }
  if (msg.data.type === 'select_child') {
    return (
      <LocationSelectMessage
        data={msg.data}
        isActive={isActive}
        isStreaming={isStreaming}
        onSelect={onSelect}
      />
    )
  }
  if (msg.data.type === 'scene_ready') {
    return <SceneReadyMessage data={msg.data} />
  }
  return <pre className={styles.text}>{JSON.stringify(msg.data, null, 2)}</pre>
}

export default function MessageList({ messages, pending, onSelect }) {
  const isEmpty = messages.length === 0 && !pending

  if (isEmpty) {
    return <p className={styles.empty}>Начни игру — отправь первое сообщение.</p>
  }

  // only the last structured bot message is interactive
  let lastDataIdx = -1
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'bot' && messages[i].data) {
      lastDataIdx = i
      break
    }
  }

  const isStreaming = !!pending

  return (
    <ul className={styles.list}>
      {messages.map((msg, i) => (
        <li key={i} className={`${styles.message} ${styles[msg.role]}`}>
          <span className={styles.role}>{ROLE_LABEL[msg.role] ?? msg.role}</span>
          {msg.role === 'bot'
            ? renderBotContent(msg, i === lastDataIdx, isStreaming, onSelect)
            : <pre className={styles.text}>{msg.displayText ?? msg.text}</pre>
          }
        </li>
      ))}
      {pending && (
        <PendingMessage
          statusLabel={pending.statusLabel}
          thinkingMs={pending.thinkingMs}
          elapsed={pending.elapsed}
        />
      )}
    </ul>
  )
}
