from dataclasses import dataclass

from app.db.mapper import bool_col


@dataclass
class LocationLevel:
    __table__ = "location_levels"
    __pk__    = "level_uid"

    level_uid:     str
    location_uid:  str
    z:             int
    display_name:  str

    is_accessible: bool = bool_col(default=True)
