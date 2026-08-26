"""Result of FineChunkRunner.refine_rects — explicit contract (not a growing tuple)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.generators.terrain.relief.discover.timings import (
    GradePipelineTimings,
)
from app.application.worldData.persistResult import PersistResult
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem


@dataclass(frozen=True)
class FineRefineResult:
    persist: PersistResult
    wilderness_chunks_written: int
    rect_count: int
    meter_surface_z: dict[tuple[int, int], int] = field(default_factory=dict)
    grade_instances: tuple[ReliefGradeInstance, ...] = ()
    grade_systems: tuple[ReliefGradeSystem, ...] = ()
    # Mill leftover ``GradeRimRay`` acc — not SCH-GRADE-CELL-SLOTS.
    mill_rim_rays: tuple[GradeRimRay, ...] = ()
    materialize_s: float = 0.0
    grade_s: float = 0.0
    pipeline_s: GradePipelineTimings = field(default_factory=GradePipelineTimings)

    @classmethod
    def empty(cls) -> FineRefineResult:
        return cls(PersistResult.from_counts(0, 0), 0, 0, {})
