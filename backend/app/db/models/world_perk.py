from dataclasses import dataclass

from app.db.mapper import json_nullable_col


@dataclass
class WorldPerk:
    __table__          = "world_perks"
    __pk__             = "perk_uid"
    __update_exclude__ = frozenset({"world_id"})

    perk_uid:            str
    world_id:            str
    system_name:         str
    display_name:        str

    system_description:  str | None = None
    display_description: str | None = None
    system_rank_value:   list | None = json_nullable_col()
    display_rank_value:  str | None = None
    system_tags:         list | None = json_nullable_col()
    display_tags:        str | None = None
    system_condition:    str | None = None
    display_condition:   str | None = None
    terrain_access:      list | None = json_nullable_col()
