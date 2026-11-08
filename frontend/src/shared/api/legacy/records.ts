export interface SessionSummary {
  id: string
  world_uid: string
  world_name: string | null
  character_id: string
  character_name: string | null
  last_active_at: string
}

export interface GameSession {
  id: string
  world_uid: string
  player_character_id: string
  created_at: string
  last_active_at: string
  restored_from_snapshot_id: string | null
}

export interface WorldSummary {
  world_uid: string
  name: string
}

export interface CharacterSummary {
  character_uid: string
  display_name: string
  display_class?: string | null
  display_gender?: string | null
  active_session?: {
    world_uid: string
    world_name: string | null
  } | null
}
