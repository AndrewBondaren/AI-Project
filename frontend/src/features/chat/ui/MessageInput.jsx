import { useState } from 'react'
import styles from './MessageInput.module.css'

export default function MessageInput({ onSend, disabled }) {
  const [text, setText] = useState('')

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const submit = () => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
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
        disabled={disabled}
      />
      <button
        className={styles.sendBtn}
        onClick={submit}
        disabled={disabled || !text.trim()}
      >
        Отправить
      </button>
    </div>
  )
}
