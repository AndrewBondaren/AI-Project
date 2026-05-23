import { streamChat, cancelStream } from '@/api/chatApi'

const DEFAULT_PROVIDER = 'qwen'
const DEFAULT_MODEL    = 'qwen3:14b'

export async function startStream(sessionId, message, requestId, resume) {
  const res = await streamChat({
    sessionId,
    message,
    requestId,
    resume,
    llmProvider: DEFAULT_PROVIDER,
    model:       DEFAULT_MODEL,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail ?? data.error ?? `HTTP ${res.status}`)
  }
  return res.body.getReader()
}

export { cancelStream }
