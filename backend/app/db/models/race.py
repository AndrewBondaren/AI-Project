from dataclasses import dataclass

from app.db.mapper import json_nullable_col


@dataclass
class Race:
    __table__ = "races"
    __pk__    = "race_uid"

    race_uid:     str
    world_id:     str
    display_race: str
    created_at:   str

    race_traits:  dict | None = json_nullable_col()
    male:         dict | None = json_nullable_col()
    female:       dict | None = json_nullable_col()
    asexual:      dict | None = json_nullable_col()
    both:         dict | None = json_nullable_col()
