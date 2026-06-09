"""
Straight staircase — один марш, строго одно направление.
ТЗ: docs/tz_staircase_generation.md § 4
"""
from app.application.worldData.generators.structure.staircase._base import StaircaseBuilder


class StraightBuilder(StaircaseBuilder):
    def build(self) -> tuple[tuple[int, int], tuple[int, int]]:
        raise NotImplementedError("StraightBuilder not yet implemented")
