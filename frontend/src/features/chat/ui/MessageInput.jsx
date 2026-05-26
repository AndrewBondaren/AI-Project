import { useState } from 'react'
import styles from './MessageInput.module.css'

const LIMIT_OPTIONS = [
  { value: 20,   label: '20' },
  { value: 50,   label: '50' },
  { value: 200,  label: '200' },
  { value: null, label: 'Все' },
]

export default function MessageInput({ onSend, onCancel, isStreaming, disabled, historyLimit, onHistoryLimitChange }) {
  const [text, setText] = useState('')
  const isBlocked = isStreaming || disabled

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !isBlocked) {
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
        disabled={isBlocked}
      />
      <div className={styles.toolbar}>
        <select
          className={styles.limitSelect}
          value={historyLimit ?? ''}
          onChange={e => onHistoryLimitChange(e.target.value === '' ? null : Number(e.target.value))}
          title="Сообщений в истории"
          disabled={isStreaming}
        >
          {LIMIT_OPTIONS.map(o => (
            <option key={o.label} value={o.value ?? ''}>{o.label}</option>
          ))}
        </select>
        {isStreaming ? (
          <button className={`${styles.actionBtn} ${styles.cancelBtn}`} onClick={onCancel} title="Отменить">
            ■
          </button>
        ) : (
          <button
            className={`${styles.actionBtn} ${styles.sendBtn}`}
            onClick={submit}
            disabled={!text.trim() || disabled}
            title="Отправить"
          >
            ↑
          </button>
        )}
      </div>
    </div>
  )
}
