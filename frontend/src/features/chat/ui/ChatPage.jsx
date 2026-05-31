import { useRef, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useChatStream } from '../hooks/useChatStream'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import styles from './ChatPage.module.css'

export default function ChatPage() {
  const { sessionId } = useParams()
  const [historyLimit, setHistoryLimit] = useState(50)
  const { messages, isStreaming, statusLabel, thinkingMs, elapsed, canResume, historyLoaded, send, resume, cancel } = useChatStream(sessionId, historyLimit)
  const scrollRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    requestAnimationFrame(() => { el.scrollTop = el.scrollHeight })
  }, [messages, isStreaming])

  const pending = isStreaming
    ? { statusLabel, thinkingMs, elapsed, onCancel: cancel }
    : null

  return (
    <div className={styles.page}>
      <div ref={scrollRef} className={styles.messageArea}>
        <MessageList messages={messages} pending={pending} onSelect={send} />
      </div>

      {canResume && !isStreaming && (
        <div className={styles.resumeBar}>
          <span className={styles.resumeHint}>Запрос был прерван.</span>
          <button className={styles.resumeBtn} onClick={resume}>Продолжить</button>
        </div>
      )}

      <div className={styles.inputBar}>
        <MessageInput
          onSend={send}
          onCancel={cancel}
          isStreaming={isStreaming}
          disabled={!historyLoaded}
          historyLimit={historyLimit}
          onHistoryLimitChange={setHistoryLimit}
        />
      </div>
    </div>
  )
}
