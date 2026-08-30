from dataclasses import dataclass

from app.db.mapper import bool_col, json_nullable_col


@dataclass
class LocationEntryPoint:
    __table__ = "location_entry_points"
    __pk__ = "entry_uid"

    entry_uid: str
    location_uid: str
    x: int
    y: int
    z: int
    display_name: str
    entry_role: str

    leads_to_level_uid: str | None = None
    entry_difficulty_override: int | None = None
    guard_level_override: int | None = None
    is_discovered: bool = bool_col(default=True)
    is_accessible: bool = bool_col(default=True)
    glossary_ref: str | None = None
    tag_refs: list | None = json_nullable_col()
