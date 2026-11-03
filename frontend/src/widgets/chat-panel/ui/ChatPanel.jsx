import { useRef, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useChatStream } from '@/features/send-message/model/useChatStream'
import MessageList from '@/entities/message/ui/MessageList'
import MessageInput from '@/features/send-message/ui/MessageInput'

export default function ChatPanel() {
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
    <div className="flex h-full flex-col overflow-hidden">
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-7">
        <MessageList messages={messages} pending={pending} onSelect={send} />
      </div>

      {canResume && !isStreaming && (
        <div className="flex items-center gap-3 border-t border-line bg-panel px-4 py-2 text-xs text-muted">
          <span className="flex-1 italic">Запрос был прерван.</span>
          <button className="rounded border border-line bg-accent/7 px-3 py-1 text-xs text-accent hover:bg-accent/15" onClick={resume}>Продолжить</button>
        </div>
      )}

      <div className="bg-background px-4 py-4 sm:px-7">
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
