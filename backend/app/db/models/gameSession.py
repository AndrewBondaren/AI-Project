from dataclasses import dataclass


@dataclass
class GameSession:
    __table__ = "game_sessions"
    __pk__    = "id"

    id:                        str
    world_id:                  str
    player_character_id:       str
    created_at:                str
    last_active_at:            str
    restored_from_snapshot_id: str | None = None
