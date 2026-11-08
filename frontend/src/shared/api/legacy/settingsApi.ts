import { request } from '../transport/http'

interface ChatSettings {
  max_tokens: number
  repair_iterations: number
  repair_mode: string
  language: string
  max_passes: number
}

export async function getSettings(): Promise<ChatSettings> {
  const res = await request(`/chat/settings`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function updateSettings(settings: ChatSettings): Promise<ChatSettings> {
  const res = await request(`/chat/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
