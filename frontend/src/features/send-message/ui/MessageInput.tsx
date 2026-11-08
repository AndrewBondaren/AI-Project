import type { KeyboardEvent } from 'react'
import { useState } from 'react'

interface MessageInputProps {
  onSend: (text: string) => void
  onCancel: () => void
  isStreaming: boolean
  disabled: boolean
  historyLimit: number | null
  onHistoryLimitChange: (limit: number | null) => void
}

const LIMIT_OPTIONS = [
  { value: 20,   label: '20' },
  { value: 50,   label: '50' },
  { value: 200,  label: '200' },
  { value: null, label: 'Все' },
]

export default function MessageInput({ onSend, onCancel, isStreaming, disabled, historyLimit, onHistoryLimitChange }: MessageInputProps) {
  const [text, setText] = useState('')
  const isBlocked = isStreaming || disabled

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
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
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-[minmax(0,1fr)_auto]">
      <textarea
        className="max-h-44 min-h-14 w-full resize-y rounded-lg border border-white/7 bg-raised px-5 py-3 text-foreground focus:border-line-hover focus:outline-none disabled:opacity-50"
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Опишите своё действие..."
        aria-label="Ваше действие"
        rows={2}
        disabled={isBlocked}
      />
      <div className="flex items-center justify-between gap-2">
        <select
          className="max-w-18 rounded-lg border border-line bg-raised p-2 text-muted"
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
          <button className="grid size-11 shrink-0 place-items-center rounded-lg border border-line bg-accent/7 enabled:hover:bg-white/10 text-danger" onClick={onCancel} title="Отменить">
            ■
          </button>
        ) : (
          <button
            className="grid size-11 shrink-0 place-items-center rounded-lg border border-line bg-accent/7 enabled:hover:bg-white/10 disabled:opacity-40"
            onClick={submit}
            disabled={!text.trim() || disabled}
            title="Отправить"
          >
            <img src="/icons/send.svg" alt="" width="24" height="24" />
          </button>
        )}
      </div>
      <span className="col-span-full text-center text-[10px] text-muted sm:text-xs">Enter — отправить · Shift+Enter — новая строка</span>
    </div>
  )
}
