"""Global ``building_templates`` library row."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.db.mapper import json_col


@dataclass
class BuildingTemplateRow:
    __table__ = "building_templates"
    __pk__ = "template_uid"

    template_uid: str
    system_name: str
    display_name: str
    structure_type: str | None  # Legacy outline metadata; typed building bodies use None.
    version: str = "1.0"
    data: dict = json_col(default_factory=dict)
    source_file: str | None = None
