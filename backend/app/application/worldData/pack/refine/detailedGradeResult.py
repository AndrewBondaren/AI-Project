"""Detailed-bake outdoor grade output — R36u single-writer contract."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance

Coord = tuple[int, int]


@dataclass(frozen=True)
class DetailedGradeResult:
    """Grade uid bag + instances produced on meter grid during L2 refine."""

    surface_grade_uid: dict[Coord, str] = field(default_factory=dict)
    grade_instances: tuple[ReliefGradeInstance, ...] = ()

    @classmethod
    def empty(cls) -> DetailedGradeResult:
        return cls()
