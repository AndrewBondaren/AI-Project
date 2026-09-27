"""Global ``structure_templates`` library row (5o split, model A).

``template_uid`` == ``StructureTemplate.system_name`` (uuid from JSON — not
uuid5 of a name). No ``system_name`` / ``owner_world_uid`` columns.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.dataModel.structure.building.structureTemplate import StructureTemplate
from app.db.mapper import json_col


def _default_structure_version() -> str:
    return str(StructureTemplate.model_fields["version"].default)


@dataclass
class StructureTemplateRow:
    __table__ = "structure_templates"
    __pk__ = "template_uid"

    template_uid: str
    display_name: str
    version: str = field(default_factory=_default_structure_version)
    data: dict = json_col(default_factory=dict)
    source_file: str | None = None
