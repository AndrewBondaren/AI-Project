import { API_URL } from '@/config'

export async function streamChat({ sessionId, message, requestId, resume = false, llmProvider, model }) {
  return fetch(`${API_URL}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id:   sessionId,
      message,
      request_id:   requestId,
      resume,
      llm_provider: llmProvider,
      model,
      meta:         {},
    }),
  })
}

export async function cancelStream(requestId) {
  await fetch(`${API_URL}/chat/stream/${requestId}`, { method: 'DELETE' })
}

export async function getHistory(sessionId, limit) {
  const params = new URLSearchParams({ session_id: sessionId })
  if (limit != null) params.set('limit', limit)
  const res = await fetch(`${API_URL}/chat/history?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getPending(sessionId) {
  const res = await fetch(`${API_URL}/chat/pending?session_id=${sessionId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()  // null | {player_input, has_snapshot}
}
