"""Global ``relief_templates`` library row — tz_terrain_relief R11/R29."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.mapper import json_col


def _default_relief_version() -> str:
    return str(ReliefTemplate.model_fields["version"].default)


@dataclass
class ReliefTemplateRow:
    __table__ = "relief_templates"
    __pk__ = "template_uid"

    template_uid: str
    system_name: str
    display_name: str
    context: str
    version: str = field(default_factory=_default_relief_version)
    data: dict = json_col(default_factory=dict)
    source_file: str | None = None
