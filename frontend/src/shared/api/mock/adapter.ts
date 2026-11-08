import type { GameApi, SendMessageInput } from '../contracts'
import type { ChatEvent, ChatMessage } from '@/shared/types/chat'
import type { FileSource } from '@/shared/types/files'
import { NetworkError } from '../transport/http'
import { readSse } from '../transport/sse'
import { demoWorlds, demoCharacters, demoSession, demoHistory } from './fixtures'

const scenario = import.meta.env.VITE_MOCK_SCENARIO
const populated = scenario !== 'empty'
const worlds = populated ? [...demoWorlds] : []
const characters = populated ? [...demoCharacters] : []
const sessions = populated ? [demoSession] : []
const histories = new Map<string, ChatMessage[]>(populated ? [[demoSession.id, [...demoHistory]]] : [])
const pending = new Map<string, ChatMessage>()
const active = new Map<string, { sessionId: string; cancel: () => void }>()

async function delay() {
  await new Promise(resolve => setTimeout(resolve, 300))
  if (scenario === 'network-error') throw new NetworkError()
}

function getSession(id: string) {
  const session = sessions.find(s => s.id === id)
  if (!session) throw new Error('Сессия не найдена')
  return session
}

function sourceName(source: FileSource) {
  return (source.file?.name ?? source.path?.split(/[\\/]/).at(-1) ?? 'Импорт').replace(/\.[^.]+$/, '')
}

function mockStream(input: SendMessageInput): AsyncIterable<ChatEvent> {
  const { sessionId, requestId } = input
  const session = getSession(sessionId)
  if ([...active.values()].some(request => request.sessionId === sessionId)) {
    throw new Error('В этой сессии уже выполняется запрос')
  }

  const previous = input.resume ? pending.get(sessionId) : undefined
  const message = previous ?? { role: 'user', text: input.message, displayText: input.displayText }
  const history = histories.get(sessionId) ?? []
  pending.set(sessionId, message)
  const encoder = new TextEncoder()
  let timer: ReturnType<typeof setTimeout> | undefined
  const clear = () => {
    clearTimeout(timer)
    active.delete(requestId)
  }
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const emit = (event: ChatEvent) => controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
      const finish = (event: ChatEvent) => {
        clear()
        emit(event)
        controller.close()
      }
      active.set(requestId, { sessionId, cancel: () => finish({ type: 'cancelled' }) })
      emit({ type: 'status', phase: 'executing', taskType: 'demo' })
      timer = setTimeout(() => {
        emit({ type: 'thinking', elapsedMs: 450 })
        timer = setTimeout(() => {
          if (scenario === 'stream-error') {
            pending.delete(sessionId)
            finish({ type: 'error', message: 'Тестовая ошибка потока.' })
            return
          }
          const response = `Ваше действие: «${message.displayText ?? message.text}». Вдали слышится шорох. Что вы сделаете дальше?`
          history.push(message, { role: 'bot', text: response })
          histories.set(sessionId, history)
          session.lastActiveAt = new Date().toISOString()
          pending.delete(sessionId)
          finish({ type: 'result', response })
        }, 650)
      }, 450)
    },
    cancel: clear,
  })
  return readSse(body, payload => payload as ChatEvent)
}

export const mockApi: GameApi = {
  async listWorlds() {
    await delay()
    return structuredClone(worlds)
  },
  async listCharacters() {
    await delay()
    return characters.map(character => {
      const session = sessions.find(s => s.characterId === character.id)
      return { ...character, activeSession: session ? { worldId: session.worldId, worldName: session.worldName } : null }
    })
  },
  async listSessions() {
    await delay()
    return structuredClone(sessions)
  },
  async createSession(worldId, characterId) {
    await delay()
    const world = worlds.find(w => w.id === worldId)
    const character = characters.find(c => c.id === characterId)
    if (!world || !character) throw new Error('Мир или персонаж не найден')
    const existing = sessions.find(s => s.worldId === worldId && s.characterId === characterId)
    if (existing) return { id: existing.id }
    const id = crypto.randomUUID()
    sessions.push({ id, worldId, characterId, worldName: world.name, characterName: character.name, lastActiveAt: new Date().toISOString() })
    return { id }
  },
  async deleteSession(id) {
    await delay()
    const session = getSession(id)
    for (const request of active.values()) if (request.sessionId === id) request.cancel()
    sessions.splice(sessions.indexOf(session), 1)
    histories.delete(id)
    pending.delete(id)
  },
  async copyCharacter(id) {
    await delay()
    const character = characters.find(c => c.id === id)
    if (!character) throw new Error('Персонаж не найден')
    const copy = { ...character, id: crypto.randomUUID() }
    characters.push(copy)
    return { id: copy.id }
  },
  async deleteCharacter(id) {
    await delay()
    const index = characters.findIndex(c => c.id === id)
    if (index === -1) throw new Error('Персонаж не найден')
    characters.splice(index, 1)
    for (const session of sessions) if (session.characterId === id) session.characterName = null
  },
  async importWorld(source) {
    await delay()
    worlds.push({ id: crypto.randomUUID(), name: sourceName(source) })
  },
  async importCharacter(source) {
    await delay()
    const id = crypto.randomUUID()
    characters.push({ id, name: sourceName(source) })
    return { id }
  },
  async getHistory(sessionId, limit) {
    await delay()
    getSession(sessionId)
    const history = histories.get(sessionId) ?? []
    return structuredClone(limit === null ? history : history.slice(Math.max(0, history.length - limit)))
  },
  async getPending(sessionId) {
    await delay()
    const text = pending.get(sessionId)?.text
    return text === undefined ? null : { text }
  },
  async streamMessage(input) {
    if (scenario === 'network-error') await delay()
    return mockStream(input)
  },
  async cancelMessage(id) {
    active.get(id)?.cancel()
  },
}
