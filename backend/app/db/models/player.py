from dataclasses import dataclass

from app.db.mapper import bool_col, json_col


@dataclass
class Player:
    __table__         = "character_sheet"
    __pk__            = "character_uid"
    __discriminator__ = {"character_type": "player"}

    character_uid:        str
    display_name:         str
    created_at:           str
    system_alive:         bool = bool_col(default=True)
    system_conscious:     bool = bool_col(default=True)
    system_race:          str | None = None
    system_location:      str | None = None
    system_stats:         dict = json_col(default_factory=dict)
    world_schema_version: str | None = None
