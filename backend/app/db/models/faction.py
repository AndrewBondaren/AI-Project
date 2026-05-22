from dataclasses import dataclass


@dataclass
class Faction:
    __table__ = "factions"
    __pk__    = "faction_uid"

    faction_uid:         str
    world_uid:            str
    display_name:        str
    created_at:          str

    system_type:         str | None = None
    display_type:        str | None = None
    system_description:  str | None = None
    display_description: str | None = None
