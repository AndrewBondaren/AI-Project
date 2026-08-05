"""World-scoped ``relief_grade_instances`` row — tz_terrain_relief R36j §8c."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.mapper import bool_col, json_col


@dataclass
class ReliefGradeInstanceRow:
    __table__ = "relief_grade_instances"
    __pk__ = "grade_uid"

    grade_uid: str
    world_uid: str
    kind: str
    height_cells: int
    length_cells: int
    cell_refs: list = json_col(default_factory=list)  # [[lx,ly], ...]
    created_at: str = ""
    angle_deg: float | None = None
    facing: str | None = None
    earthen_canal: bool = bool_col(default=False)
    structure_refs: list = json_col(default_factory=list)  # barrier refs
    structure_canal: str | None = None  # canal_template_registry system_type
    template_uid: str | None = None
    edge_uid: str | None = None
    site_id: str | None = None
    grade_system_uid: str | None = None
