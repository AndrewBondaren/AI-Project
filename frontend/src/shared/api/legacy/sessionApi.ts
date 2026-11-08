import type { GameSession, SessionSummary } from './records'
import { request } from '../transport/http'

export async function listSessions(): Promise<SessionSummary[]> {
  const res = await request(`/sessions`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function createSession(worldUid: string, characterId: string): Promise<GameSession> {
  const res = await request(`/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ world_uid: worldUid, character_id: characterId }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function getSession(sessionId: string): Promise<GameSession> {
  const res = await request(`/sessions/${sessionId}`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function deleteSession(sessionId: string) {
  const res = await request(`/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail ?? `HTTP ${res.status}`)
  }
}
