from dataclasses import dataclass

from app.db.mapper import bool_col


@dataclass
class LocationPassage:
    __table__ = "location_passages"
    __pk__    = "passage_uid"

    passage_uid:     str
    world_uid:       str
    to_level_uid:    str
    to_x:            int
    to_y:            int
    system_passage_type: str

    from_level_uid:  str | None = None   # null = внешнее пространство (entry_point)
    from_x:          int | None = None
    from_y:          int | None = None

    is_bidirectional: bool     = bool_col(default=True)
    display_name:     str | None = None
    glossary_ref:     str | None = None
    tag_refs:         str | None = None
