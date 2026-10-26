"""State row for one transition side; composite PK is owned by aggregate writer."""

from dataclasses import dataclass, field


@dataclass
class TransitionSideRow:
    __table__ = "transition_sides"
    __pk__ = "transition_uid"  # composite (transition_uid, side); no BaseRepository CRUD

    transition_uid: str
    side: str
    owner_location_uid: str | None
    is_discovered: bool = field(metadata={"db_type": "bool"})
    is_accessible: bool = field(metadata={"db_type": "bool"})
    entry_difficulty_override: int | None
    guard_level_override: int | None
    display_name: str | None
