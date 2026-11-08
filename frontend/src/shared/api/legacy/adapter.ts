import type { GameApi } from '../contracts'
import { readSse } from '../transport/sse'
import { isStructuredMessage, type ChatEvent } from '@/shared/types/chat'
import * as worlds from './worldApi'
import * as sessions from './sessionApi'
import * as chat from './chatApi'

function normalizeResponse(value: unknown): unknown {
  if (!isStructuredMessage(value)) return value
  if (value.type === 'select_child' && Array.isArray(value.children)) {
    return {
      type: 'selectLocation',
      parent: value.parent,
      children: value.children.map(child => ({
        id: child.uid,
        name: child.name,
        typeLabel: child.type_display,
        stateName: child.state_name,
        isHome: child.is_home,
      })),
    }
  }
  if (value.type === 'scene_ready') return { ...value, type: 'sceneReady' }
  return value
}

function decodeLegacyEvent(value: unknown): ChatEvent | undefined {
  if (!isStructuredMessage(value)) return
  switch (value.type) {
    case 'node_status':
      if ('phase' in value && typeof value.phase === 'string') {
        const taskType = 'task_type' in value && typeof value.task_type === 'string' ? value.task_type : undefined
        return { type: 'status', phase: value.phase, taskType }
      }
      return
    case 'thinking':
      if ('elapsed_ms' in value && typeof value.elapsed_ms === 'number') {
        return { type: 'thinking', elapsedMs: value.elapsed_ms }
      }
      return
    case 'result':
      return { type: 'result', response: normalizeResponse(value.response) }
    case 'cancelled':
      return { type: 'cancelled' }
    case 'error':
      if ('message' in value && typeof value.message === 'string') return { type: 'error', message: value.message }
  }
}

export const legacyApi: GameApi = {
  async listWorlds() {
    return (await worlds.getWorlds()).map(w => ({ id: w.world_uid, name: w.name }))
  },
  async listCharacters() {
    return (await worlds.getCharacters()).map(c => ({
      id: c.character_uid,
      name: c.display_name,
      characterClass: c.display_class,
      gender: c.display_gender,
      activeSession: c.active_session ? {
        worldId: c.active_session.world_uid,
        worldName: c.active_session.world_name,
      } : null,
    }))
  },
  async listSessions() {
    return (await sessions.listSessions()).map(s => ({
      id: s.id,
      worldId: s.world_uid,
      worldName: s.world_name,
      characterId: s.character_id,
      characterName: s.character_name,
      lastActiveAt: s.last_active_at,
    }))
  },
  async createSession(worldId, characterId) {
    const { id } = await sessions.createSession(worldId, characterId)
    return { id }
  },
  deleteSession: sessions.deleteSession,
  async copyCharacter(id) {
    return { id: (await worlds.copyCharacter(id)).character_uid }
  },
  deleteCharacter: worlds.deleteCharacter,
  async importWorld(source) {
    await worlds.importWorld(source)
  },
  async importCharacter(source) {
    return { id: (await worlds.importCharacter(source)).character_uid }
  },
  async getHistory(sessionId, limit) {
    const history = await chat.getHistory(sessionId, limit)
    return history.map(message => {
      if (message.role !== 'bot' || !message.text) return message
      try {
        const parsed = normalizeResponse(JSON.parse(message.text))
        return isStructuredMessage(parsed) ? { role: 'bot', data: parsed } : message
      } catch {
        return message
      }
    })
  },
  async getPending(sessionId) {
    const pending = await chat.getPending(sessionId)
    return pending ? { text: pending.player_input } : null
  },
  async streamMessage(input) {
    const res = await chat.streamChat({ ...input, llmProvider: 'qwen', model: 'qwen3:14b' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail ?? data.error ?? `HTTP ${res.status}`)
    }
    if (!res.body) throw new Error('Ответ чата не содержит поток данных')
    return readSse(res.body, decodeLegacyEvent)
  },
  cancelMessage: chat.cancelStream,
}
