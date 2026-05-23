from dataclasses import dataclass


@dataclass
class SessionSummary:
    id:             str
    world_uid:      str
    world_name:     str | None
    character_id:   str
    character_name: str | None
    last_active_at: str
