import { useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useChatStream } from '../hooks/useChatStream'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import StatusBar from './StatusBar'
import styles from './ChatPage.module.css'

export default function ChatPage() {
  const { sessionId } = useParams()
  const { messages, isStreaming, statusLabel, thinkingMs, elapsed, canResume, send, resume, cancel } = useChatStream(sessionId)
  const scrollRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    requestAnimationFrame(() => { el.scrollTop = el.scrollHeight })
  }, [messages, isStreaming])

  return (
    <div className={styles.page}>
      <div ref={scrollRef} className={styles.messageArea}>
        <MessageList messages={messages} />
      </div>

      {isStreaming && (
        <StatusBar
          statusLabel={statusLabel}
          thinkingMs={thinkingMs}
          elapsed={elapsed}
          onCancel={cancel}
        />
      )}

      {canResume && !isStreaming && (
        <div className={styles.resumeBar}>
          <span className={styles.resumeHint}>Запрос был отменён.</span>
          <button className={styles.resumeBtn} onClick={resume}>Продолжить</button>
        </div>
      )}

      <div className={styles.inputBar}>
        <MessageInput onSend={send} disabled={isStreaming} />
      </div>
    </div>
  )
}
