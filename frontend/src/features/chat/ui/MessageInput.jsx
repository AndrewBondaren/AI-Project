import { useState } from 'react'
import styles from './MessageInput.module.css'

export default function MessageInput({ onSend, onCancel, isStreaming }) {
  const [text, setText] = useState('')

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !isStreaming) {
      e.preventDefault()
      submit()
    }
  }

  const submit = () => {
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText('')
  }

  return (
    <div className={styles.wrapper}>
      <textarea
        className={styles.input}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Введи действие... (Enter — отправить, Shift+Enter — новая строка)"
        rows={2}
        disabled={isStreaming}
      />
      {isStreaming ? (
        <button className={`${styles.actionBtn} ${styles.cancelBtn}`} onClick={onCancel} title="Отменить">
          ■
        </button>
      ) : (
        <button
          className={`${styles.actionBtn} ${styles.sendBtn}`}
          onClick={submit}
          disabled={!text.trim()}
          title="Отправить"
        >
          ↑
        </button>
      )}
    </div>
  )
}
