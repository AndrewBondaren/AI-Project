"""Global perk template library row — tz_world_bundle WB-14."""

from dataclasses import dataclass

from app.db.mapper import json_nullable_col


@dataclass
class WorldPerk:
    """Row in ``perk_templates`` (legacy class name kept for import sites)."""

    __table__ = "perk_templates"
    __pk__ = "template_uid"

    template_uid: str
    system_name: str
    display_name: str

    system_description: str | None = None
    display_description: str | None = None
    system_rank_value: list | None = json_nullable_col()
    display_rank_value: str | None = None
    system_tags: list | None = json_nullable_col()
    display_tags: str | None = None
    system_condition: str | None = None
    display_condition: str | None = None
    terrain_access: list | None = json_nullable_col()
