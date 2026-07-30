"""Global race template library row — tz_world_bundle WB-13."""

from dataclasses import dataclass

from app.db.mapper import json_nullable_col


@dataclass
class Race:
    __table__ = "race_templates"
    __pk__ = "template_uid"

    template_uid: str
    system_name: str
    display_name: str
    created_at: str

    race_traits: dict | None = json_nullable_col()
    male: dict | None = json_nullable_col()
    female: dict | None = json_nullable_col()
    asexual: dict | None = json_nullable_col()
    both: dict | None = json_nullable_col()
