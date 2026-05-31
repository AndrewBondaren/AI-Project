from dataclasses import dataclass


@dataclass
class State:
    __table__ = "states"
    __pk__    = "state_uid"

    state_uid:       str
    world_uid:       str
    display_name:    str
    created_at:      str
    government_type: str | None = None
    display_description: str | None = None
