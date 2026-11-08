import { isStructuredMessage } from '@/shared/types/chat'
import type { ChatEvent, ChatMessage, StreamStatus } from '@/shared/types/chat'
import { errorMessage } from '@/shared/lib/errorMessage'
import { useCallback, useEffect, useRef, useState } from 'react'
import { startStream, cancelStream } from '../api/sendMessage'
import { getHistory, getPending } from '@/shared/api/chatApi'

export function useChatStream(sessionId: string, historyLimit: number | null) {
  const [messages,      setMessages]      = useState<ChatMessage[]>([])
  const [isStreaming,   setIsStreaming]   = useState(false)
  const [statusLabel,   setStatusLabel]   = useState<StreamStatus | null>(null)
  const [thinkingMs,    setThinkingMs]    = useState<number | null>(null)
  const [elapsed,       setElapsed]       = useState(0)
  const [canResume,     setCanResume]     = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [streamError, setStreamError] = useState<string | null>(null)
  const [historyAttempt, setHistoryAttempt] = useState(0)

  const requestIdRef   = useRef<string | null>(null)
  const lastMessageRef = useRef<string | null>(null)
  const timerRef       = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const startTimeRef   = useRef(0)

  useEffect(() => {
    let current = true
    setHistoryLoaded(false)
    setHistoryError(null)
    setCanResume(false)
    Promise.all([
      getHistory(sessionId, historyLimit),
      getPending(sessionId).catch(() => null),
    ])
      .then(([history, pending]) => {
        if (!current) return
        const msgs = [...history]
        lastMessageRef.current = pending?.text ?? null
        if (pending) {
          msgs.push({ role: 'pending', text: pending.text })
          setCanResume(true)
        }
        setMessages(msgs)
        setHistoryLoaded(true)
      })
      .catch(error => {
        if (current) setHistoryError(errorMessage(error))
      })
    return () => { current = false }
  }, [sessionId, historyLimit, historyAttempt])

  useEffect(() => () => clearInterval(timerRef.current), [])

  const startTimer = () => {
    startTimeRef.current = Date.now()
    setElapsed(0)
    timerRef.current = setInterval(() => {
      setElapsed(Date.now() - startTimeRef.current)
    }, 100)
  }

  const stopTimer = () => {
    clearInterval(timerRef.current)
    timerRef.current = undefined
  }

  const handleEvent = useCallback((event: ChatEvent) => {
    switch (event.type) {
      case 'status':
        setStatusLabel({ phase: event.phase, taskType: event.taskType })
        setThinkingMs(null)
        break
      case 'thinking':
        setThinkingMs(event.elapsedMs)
        break
      case 'result': {
        const response = event.response
        if (isStructuredMessage(response)) {
          setMessages(prev => [...prev, { role: 'bot', data: response }])
        } else {
          const text = typeof response === 'string' ? response : JSON.stringify(response, null, 2)
          setMessages(prev => [...prev, { role: 'bot', text }])
        }
        break
      }
      case 'cancelled':
        setMessages(prev => [...prev, { role: 'system', text: 'Отменено' }])
        setCanResume(true)
        break
      case 'error':
        setStreamError(event.message)
        break
    }
  }, [])

  const runStream = useCallback(async (text: string, resume = false, displayText?: string) => {
    const requestId = crypto.randomUUID()
    requestIdRef.current   = requestId
    lastMessageRef.current = text

    setIsStreaming(true)
    setCanResume(false)
    setStatusLabel(null)
    setThinkingMs(null)
    setStreamError(null)

    if (resume) {
      setMessages(prev => prev.map(m => m.role === 'pending' ? { ...m, role: 'user' } : m))
    }

    startTimer()

    try {
      const events = await startStream({ sessionId, message: text, requestId, resume, displayText })
      let completed = false
      for await (const event of events) {
        handleEvent(event)
        if (event.type === 'result' || event.type === 'cancelled' || event.type === 'error') {
          completed = true
        }
      }
      if (!completed) setStreamError('Поток прервался до получения ответа.')
    } catch (e) {
      setStreamError(errorMessage(e))
    } finally {
      requestIdRef.current = null
      stopTimer()
      setIsStreaming(false)
      setStatusLabel(null)
      setThinkingMs(null)
    }
  }, [sessionId, handleEvent])

  const send = useCallback(async (text: string, display?: string) => {
    if (!text.trim() || requestIdRef.current || !historyLoaded) return
    setCanResume(false)
    const userMsg = { role: 'user', text, ...(display ? { displayText: display } : {}) }
    setMessages(prev => [...prev.filter(m => m.role !== 'pending'), userMsg])
    await runStream(text, false, display)
  }, [historyLoaded, runStream])

  const resume = useCallback(() => {
    if (!lastMessageRef.current || requestIdRef.current) return
    runStream(lastMessageRef.current, true)
  }, [runStream])

  const cancel = useCallback(() => {
    if (requestIdRef.current) {
      void cancelStream(requestIdRef.current).catch(error => setStreamError(errorMessage(error)))
    }
  }, [])

  const retryHistory = () => setHistoryAttempt(attempt => attempt + 1)
  return { messages, isStreaming, statusLabel, thinkingMs, elapsed, canResume, historyLoaded, historyError, streamError, retryHistory, send, resume, cancel }
}
