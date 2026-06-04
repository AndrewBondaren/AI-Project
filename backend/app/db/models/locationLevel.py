from dataclasses import dataclass

from app.db.mapper import bool_col, json_col


@dataclass
class LocationLevel:
    __table__ = "location_levels"
    __pk__    = "level_uid"

    level_uid:     str
    location_uid:  str
    z:             int
    display_name:  str

    is_accessible:  bool = bool_col(default=True)
    isolated:       bool = bool_col(default=False)
    access_mechanic: list = json_col(default_factory=list)
