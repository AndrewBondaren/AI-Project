"""Bake-boundary road_shoulder intent (RELIEF-T-24 / BAR-1).

Neutral DTO — typed ``Canal`` + optional flat fence refs (T-53).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.canalAttachments import (
    CanalDrawResult,
    EMPTY_DRAW,
    build_canal,
)
from app.dataModel.terrain.relief.canal import Canal


@dataclass(frozen=True, slots=True)
class RoadShoulderIntent:
    """Data-out after shoulder grade/stamp; barrier materialize = RELIEF-BAR-1."""

    edge_uid: str
    site_id: str
    template_uid: str | None
    kind: str | None
    width: int
    cell_coords: tuple[tuple[int, int], ...]
    skipped: bool
    reason: str = ""
    canal: Canal | None = None
    # Flat fence refs when knobs carry structure_refs beside earthen canal
    extra_structure_refs: tuple[str, ...] = ()

    @property
    def earthen_canal(self) -> bool:
        return self._drawn().earthen_canal

    @property
    def structure_refs(self) -> tuple[str, ...]:
        return self._drawn().structure_refs

    @property
    def structure_canal(self) -> str | None:
        return self._drawn().structure_canal

    def _drawn(self) -> CanalDrawResult:
        if self.canal is None:
            if not self.extra_structure_refs:
                return EMPTY_DRAW
            return CanalDrawResult(
                earthen_canal=False,
                structure_refs=self.extra_structure_refs,
                structure_canal=None,
            )
        return build_canal(
            self.canal, extra_structure_refs=self.extra_structure_refs,
        )
