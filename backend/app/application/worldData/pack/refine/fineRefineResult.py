"""Result of FineChunkRunner.refine_rects — explicit contract (not a growing tuple)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.persistResult import PersistResult


@dataclass(frozen=True)
class FineRefineResult:
    persist: PersistResult
    wilderness_chunks_written: int
    rect_count: int
    meter_surface_z: dict[tuple[int, int], int] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> FineRefineResult:
        return cls(PersistResult.from_counts(0, 0), 0, 0, {})
