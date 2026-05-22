from dataclasses import dataclass

from app.db.mapper import json_col


@dataclass
class World:
    __table__ = "worlds"
    __pk__    = "id"

    id:                 str
    name:               str
    created_at:         str
    narrative_language: str  = "ru"
    measurement_system: str  = "metric"
    current_tick:       int  = 0
    stat_schema:        dict = json_col(default_factory=dict)
    skill_schema:       dict = json_col(default_factory=dict)
    combat_settings:    dict = json_col(default_factory=dict)
    calendar:           dict = json_col(default_factory=dict)
    schema_version:     str | None = None
