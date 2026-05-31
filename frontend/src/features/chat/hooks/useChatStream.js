import { useCallback, useEffect, useRef, useState } from 'react'
import { startStream, cancelStream } from '../service'
import { getHistory, getPending } from '@/api/chatApi'

export function useChatStream(sessionId, historyLimit) {
  const [messages,      setMessages]      = useState([])
  const [isStreaming,   setIsStreaming]   = useState(false)
  const [statusLabel,   setStatusLabel]   = useState(null)
  const [thinkingMs,    setThinkingMs]    = useState(null)
  const [elapsed,       setElapsed]       = useState(0)
  const [canResume,     setCanResume]     = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)

  const requestIdRef   = useRef(null)
  const lastMessageRef = useRef(null)
  const timerRef       = useRef(null)
  const startTimeRef   = useRef(null)

  useEffect(() => {
    setHistoryLoaded(false)
    setCanResume(false)
    Promise.all([
      getHistory(sessionId, historyLimit),
      getPending(sessionId).catch(() => null),
    ])
      .then(([history, pending]) => {
        const msgs = history.map(msg => {
          if (msg.role === 'bot' && msg.text) {
            try {
              const parsed = JSON.parse(msg.text)
              if (parsed && typeof parsed === 'object' && parsed.type) {
                return { role: 'bot', data: parsed }
              }
            } catch { /* plain text */ }
          }
          return msg
        })
        if (pending) {
          msgs.push({ role: 'pending', text: pending.player_input })
          lastMessageRef.current = pending.player_input
          setCanResume(true)
        }
        setMessages(msgs)
      })
      .catch(() => setMessages([]))
      .finally(() => setHistoryLoaded(true))
  }, [sessionId, historyLimit])

  const startTimer = () => {
    startTimeRef.current = Date.now()
    setElapsed(0)
    timerRef.current = setInterval(() => {
      setElapsed(Date.now() - startTimeRef.current)
    }, 100)
  }

  const stopTimer = () => {
    clearInterval(timerRef.current)
    timerRef.current = null
  }

  const handleEvent = useCallback((event) => {
    switch (event.type) {
      case 'node_status':
        setStatusLabel({ phase: event.phase, task_type: event.task_type })
        setThinkingMs(null)
        break
      case 'thinking':
        setThinkingMs(event.elapsed_ms)
        break
      case 'result': {
        const response = event.response
        if (response && typeof response === 'object' && 'type' in response) {
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
        setMessages(prev => [...prev, { role: 'bot', text: `Ошибка: ${event.message}` }])
        break
    }
  }, [])

  const processStream = useCallback(async (reader) => {
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try { handleEvent(JSON.parse(line.slice(6))) } catch { /* ignore malformed */ }
      }
    }
  }, [handleEvent])

  const runStream = useCallback(async (text, resume = false) => {
    const requestId = crypto.randomUUID()
    requestIdRef.current   = requestId
    lastMessageRef.current = text

    setIsStreaming(true)
    setCanResume(false)
    setStatusLabel(null)
    setThinkingMs(null)

    if (resume) {
      setMessages(prev => prev.map(m => m.role === 'pending' ? { ...m, role: 'user' } : m))
    }

    startTimer()

    try {
      const reader = await startStream(sessionId, text, requestId, resume)
      await processStream(reader)
    } catch (e) {
      setMessages(prev => [...prev, { role: 'bot', text: `Ошибка: ${e.message}` }])
    } finally {
      requestIdRef.current = null
      stopTimer()
      setIsStreaming(false)
      setStatusLabel(null)
      setThinkingMs(null)
    }
  }, [sessionId, processStream])

  const send = useCallback(async (text, display) => {
    if (!text.trim() || isStreaming || !historyLoaded) return
    setCanResume(false)
    const userMsg = { role: 'user', text, ...(display ? { displayText: display } : {}) }
    setMessages(prev => [...prev.filter(m => m.role !== 'pending'), userMsg])
    await runStream(text, false)
  }, [isStreaming, historyLoaded, runStream])

  const resume = useCallback(() => {
    if (!lastMessageRef.current || isStreaming) return
    runStream(lastMessageRef.current, true)
  }, [isStreaming, runStream])

  const cancel = useCallback(() => {
    if (requestIdRef.current) cancelStream(requestIdRef.current)
  }, [])

  return { messages, isStreaming, statusLabel, thinkingMs, elapsed, canResume, historyLoaded, send, resume, cancel }
}
