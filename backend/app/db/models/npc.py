from dataclasses import dataclass

from app.db.mapper import bool_col, json_col, json_nullable_col


@dataclass
class Npc:
    __table__            = "character_sheet"
    __pk__               = "character_uid"
    __discriminator__    = {"character_type": "npc"}
    __update_exclude__   = frozenset({"world_id"})

    character_uid:            str
    display_name:             str
    world_id:                 str
    created_at:               str
    system_alive:             bool       = bool_col(default=True)
    system_conscious:         bool       = bool_col(default=True)
    system_race:              str | None = None
    system_location:          str | None = None
    system_stats:             dict       = json_col(default_factory=dict)
    world_schema_version:     str | None = None
    system_current_needs:     dict       = json_col(default_factory=dict)
    system_current_target:    dict | None = json_nullable_col()
    system_npc_goal:          dict | None = json_nullable_col()
    system_current_thoughts:  str | None = None
    display_current_thoughts: str | None = None
