import { isLocationSelection, isSceneReady } from '@/shared/types/chat'
import type { ChatMessage, LocationSelectHandler, StreamStatus } from '@/shared/types/chat'
import { LocationSelectMessage, SceneReadyMessage } from './LocationSelectMessage'
import MessageBubble from './MessageBubble'

interface BotContentProps {
  message: ChatMessage
  isActive: boolean
  isStreaming: boolean
  onSelect: LocationSelectHandler
}

interface MessageListProps {
  messages: ChatMessage[]
  pending: {
    statusLabel: StreamStatus | null
    thinkingMs: number | null
    elapsed: number
  } | null
  onSelect: LocationSelectHandler
}

function buildPendingText(statusLabel: StreamStatus | null, thinkingMs: number | null, elapsed: number) {
  if (thinkingMs !== null) {
    const ms = thinkingMs > 0 ? thinkingMs : elapsed
    return `LLM думает... ${(ms / 1000).toFixed(1)}s`
  }
  if (!statusLabel) return `Обработка... ${(elapsed / 1000).toFixed(1)}s`
  const { phase, taskType: task = '' } = statusLabel
  const time = `${(elapsed / 1000).toFixed(1)}s`
  if (phase === 'repairing') return `Исправление: ${task}  ${time}`
  if (phase === 'executing') return `Выполнение: ${task}  ${time}`
  if (phase === 'done') return `Готово: ${task}  ${time}`
  return `${phase}  ${time}`
}

function BotContent({ message, isActive, isStreaming, onSelect }: BotContentProps) {
  if (!message.data) return message.text
  if (isLocationSelection(message.data)) {
    return <LocationSelectMessage data={message.data} isActive={isActive} isStreaming={isStreaming} onSelect={onSelect} />
  }
  if (isSceneReady(message.data)) return <SceneReadyMessage data={message.data} />
  return JSON.stringify(message.data, null, 2)
}

export default function MessageList({ messages, pending, onSelect }: MessageListProps) {
  if (!messages.length && !pending) {
    return <p className="mt-8 text-center text-faint italic">Начни игру — отправь первое сообщение.</p>
  }
  // Only the last structured bot message is interactive.
  const lastDataIdx = messages.findLastIndex(message => message.role === 'bot' && message.data)
  return (
    <ul className="flex flex-col gap-7" aria-label="Сообщения">
      {messages.map((message, i) => (
        <MessageBubble key={i} role={message.role}>
          {message.role === 'bot'
            ? <BotContent message={message} isActive={i === lastDataIdx} isStreaming={!!pending} onSelect={onSelect} />
            : message.displayText ?? message.text}
        </MessageBubble>
      ))}
      {pending && (
        <MessageBubble role="bot">
          <span role="status" className="flex items-center gap-2 text-muted italic">
            <span className="inline-block size-1.5 shrink-0 animate-pulse rounded-full bg-accent motion-reduce:animate-none" />
            {buildPendingText(pending.statusLabel, pending.thinkingMs, pending.elapsed)}
          </span>
        </MessageBubble>
      )}
    </ul>
  )
}
