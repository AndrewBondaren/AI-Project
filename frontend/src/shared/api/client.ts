import { USE_MOCKS } from '@/shared/config/api'
import type { GameApi } from './contracts'
import { legacyApi } from './legacy/adapter'

const adapter: Promise<GameApi> = USE_MOCKS
  ? import('./mock/adapter').then(({ mockApi }) => mockApi)
  : Promise.resolve(legacyApi)

export const api: GameApi = {
  listWorlds: async () => (await adapter).listWorlds(),
  listCharacters: async () => (await adapter).listCharacters(),
  listSessions: async () => (await adapter).listSessions(),
  createSession: async (...args) => (await adapter).createSession(...args),
  deleteSession: async (...args) => (await adapter).deleteSession(...args),
  copyCharacter: async (...args) => (await adapter).copyCharacter(...args),
  deleteCharacter: async (...args) => (await adapter).deleteCharacter(...args),
  importWorld: async (...args) => (await adapter).importWorld(...args),
  importCharacter: async (...args) => (await adapter).importCharacter(...args),
  getHistory: async (...args) => (await adapter).getHistory(...args),
  getPending: async (...args) => (await adapter).getPending(...args),
  streamMessage: async (...args) => (await adapter).streamMessage(...args),
  cancelMessage: async (...args) => (await adapter).cancelMessage(...args),
}
