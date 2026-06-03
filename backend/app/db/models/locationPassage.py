from dataclasses import dataclass

from app.db.mapper import bool_col


@dataclass
class LocationPassage:
    __table__ = "location_passages"
    __pk__    = "passage_uid"

    passage_uid:     str
    world_uid:       str
    from_level_uid:  str
    from_x:          int
    from_y:          int
    to_level_uid:    str
    to_x:            int
    to_y:            int
    passage_type:    str

    is_bidirectional: bool     = bool_col(default=True)
    display_name:     str | None = None
    glossary_ref:     str | None = None
    tag_refs:         str | None = None
