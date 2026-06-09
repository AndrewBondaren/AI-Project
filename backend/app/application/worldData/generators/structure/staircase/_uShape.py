"""
U-shape staircase — N маршей, соединённых landing у торцевых стен.
ТЗ: docs/tz_staircase_generation.md § 5
"""
from app.application.worldData.generators.structure.staircase._base import StaircaseBuilder


class UShapeBuilder(StaircaseBuilder):
    def build(self) -> tuple[tuple[int, int], tuple[int, int]]:
        raise NotImplementedError("UShapeBuilder not yet implemented")
