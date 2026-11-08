export interface SessionSummary {
  id: string
  worldId: string
  worldName: string | null
  characterId: string
  characterName: string | null
  lastActiveAt: string
}

export interface WorldSummary {
  id: string
  name: string
}

export interface CharacterSummary {
  id: string
  name: string
  characterClass?: string | null
  gender?: string | null
  activeSession?: {
    worldId: string
    worldName: string | null
  } | null
}
