import { listSessions as apiListSessions, createSession as apiCreateSession, deleteSession as apiDeleteSession } from '@/api/sessionApi'
import { getWorlds, getCharacters, importCharacterFromPath } from '@/api/worldApi'
import { openFile } from '@/platform/fileSystem'

export async function listSessions() {
  return apiListSessions()
}

export async function listWorlds() {
  return getWorlds()
}

export async function listCharacters(worldId) {
  return getCharacters(worldId)
}

export async function createSession(worldId, characterId) {
  return apiCreateSession(worldId, characterId)
}

export async function deleteSession(sessionId) {
  return apiDeleteSession(sessionId)
}

export async function importCharacter() {
  const path = await openFile({ filters: [{ name: 'JSON', extensions: ['json'] }] })
  if (!path) return null
  return importCharacterFromPath(path)
}
