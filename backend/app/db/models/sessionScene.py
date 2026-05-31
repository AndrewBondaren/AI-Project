from dataclasses import dataclass

from app.db.mapper import json_col


@dataclass
class SessionScene:
    __table__ = "session_scene"
    __pk__    = "session_id"

    session_id:   str
    description:  str
    actors:       list = json_col(default_factory=list)
    location_uid: str | None = None
    level_uid:    str | None = None
    updated_at:   str | None = None
    created_at:   str | None = None
