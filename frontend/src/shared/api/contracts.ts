import type { ChatEvent, ChatMessage } from '@/shared/types/chat'
import type { FileSource } from '@/shared/types/files'
import type { CharacterSummary, WorldSummary, SessionSummary } from '@/shared/types/records'

export interface SendMessageInput {
  sessionId: string
  requestId: string
  message: string
  displayText?: string
  resume: boolean
}

export interface PendingMessage {
  text: string
}

export interface GameApi {
  listWorlds(): Promise<WorldSummary[]>
  listCharacters(): Promise<CharacterSummary[]>
  listSessions(): Promise<SessionSummary[]>
  createSession(worldId: string, characterId: string): Promise<{ id: string }>
  deleteSession(sessionId: string): Promise<void>
  copyCharacter(characterId: string): Promise<{ id: string }>
  deleteCharacter(characterId: string): Promise<void>
  importWorld(source: FileSource): Promise<void>
  importCharacter(source: FileSource): Promise<{ id: string }>
  getHistory(sessionId: string, limit: number | null): Promise<ChatMessage[]>
  getPending(sessionId: string): Promise<PendingMessage | null>
  streamMessage(input: SendMessageInput): Promise<AsyncIterable<ChatEvent>>
  cancelMessage(requestId: string): Promise<void>
}
