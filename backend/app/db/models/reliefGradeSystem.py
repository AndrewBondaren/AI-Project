"""World-scoped ``relief_grade_systems`` row — tz_terrain_relief R36l §8c."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.mapper import json_col


@dataclass
class ReliefGradeSystemRow:
    __table__ = "relief_grade_systems"
    __pk__ = "grade_system_uid"

    grade_system_uid: str
    world_uid: str
    grade_instance_uids: list = json_col(default_factory=list)  # ordered Instance.grade_uid, ≥ 2
    created_at: str = ""
    owner_uid: str | None = None
    display_name: str | None = None
