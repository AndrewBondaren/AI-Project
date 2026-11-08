import type { ChatMessage } from '@/shared/types/chat'
import type { SendMessageInput } from '../contracts'
import { request } from '../transport/http'

type StreamChatRequest = SendMessageInput & { llmProvider: string; model: string }

export async function streamChat({ sessionId, message, requestId, resume, llmProvider, model }: StreamChatRequest) {
  return request(`/chat/stream`, {
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

export async function cancelStream(requestId: string) {
  const res = await request(`/chat/stream/${requestId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function getHistory(sessionId: string, limit: number | null): Promise<ChatMessage[]> {
  const params = new URLSearchParams({ session_id: sessionId })
  if (limit != null) params.set('limit', String(limit))
  const res = await request(`/chat/history?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getPending(sessionId: string): Promise<{ player_input: string; has_snapshot: boolean } | null> {
  const res = await request(`/chat/pending?session_id=${sessionId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()  // null | {player_input, has_snapshot}
}
