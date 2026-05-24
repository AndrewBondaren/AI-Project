import { useState } from 'react'
import styles from './StatusBar.module.css'

export default function StatusBar({ statusLabel, thinkingMs, elapsed, onCancel }) {
  const [cancelling, setCancelling] = useState(false)

  const handleCancel = () => {
    setCancelling(true)
    onCancel()
  }

  return (
    <div className={styles.bar}>
      <span className={styles.dot} />
      <span className={styles.label}>{buildText(statusLabel, thinkingMs, elapsed)}</span>
      <span className={styles.timer}>{(elapsed / 1000).toFixed(1)}s</span>
      <button className={styles.cancelBtn} onClick={handleCancel} disabled={cancelling} title="Отменить">✕</button>
    </div>
  )
}

function buildText(statusLabel, thinkingMs, elapsed) {
  if (thinkingMs !== null) {
    const ms = thinkingMs > 0 ? thinkingMs : elapsed
    return `LLM думает... ${(ms / 1000).toFixed(1)}s`
  }
  if (!statusLabel) return 'Обработка...'
  const { phase, task_type: task = '' } = statusLabel
  if (phase === 'repairing') return `Исправление: ${task}`
  if (phase === 'executing') return `Выполнение: ${task}`
  if (phase === 'done')      return `Готово: ${task}`
  return phase
}
