"""Bake-boundary road_shoulder intent (RELIEF-T-24 / BAR-1 / T-52 phase 4).

Neutral DTO + emit helper — typed ``Canal`` + optional flat fence refs.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.canalAttachments import (
    CanalDrawResult,
    knobs_extra_structure_refs,
    project_canal_draw,
)
from app.application.worldData.generators.terrain.relief.roadShoulderGrade import (
    RoadShoulderGradeResult,
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
    def earthen_canal(self) -> bool | None:
        """Drawn earthen cut; ``None`` = omit (no silent False — RELIEF-T-54)."""
        if self.canal is None:
            if self.extra_structure_refs:
                return False
            return None
        return bool(self._drawn().earthen_canal)

    @property
    def structure_refs(self) -> tuple[str, ...]:
        return self._drawn().structure_refs

    @property
    def structure_canal(self) -> str | None:
        return self._drawn().structure_canal

    def _drawn(self) -> CanalDrawResult:
        return project_canal_draw(
            self.canal, extra_structure_refs=self.extra_structure_refs,
        )


def to_intent(
    result: RoadShoulderGradeResult,
    cell_coords: tuple[tuple[int, int], ...],
    *,
    skipped: bool | None = None,
    reason: str | None = None,
    width: int | None = None,
    canal: Canal | None = None,
    extra_structure_refs: tuple[str, ...] = (),
) -> RoadShoulderIntent:
    """Emit Intent from grade result + bake canal cut (no knobs→Canal synthesize — T-61)."""
    d = result.decision
    kind = d.kind.value if d.kind is not None else None
    is_skipped = d.skipped if skipped is None else skipped
    extras = extra_structure_refs
    # Fence refs from knobs only when caller omitted extras and not skipped.
    if not extras and not is_skipped and canal is None:
        extras = knobs_extra_structure_refs(
            earthen_canal=d.earthen_canal,
            structure_canal=d.structure_canal,
            structure_refs=d.structure_refs,
        )
    return RoadShoulderIntent(
        edge_uid=result.segment.edge_uid,
        site_id=result.segment.site_id,
        template_uid=result.template_uid,
        kind=kind,
        width=d.requested_length if width is None else int(width),
        cell_coords=cell_coords,
        skipped=is_skipped,
        reason=d.reason if reason is None else reason,
        canal=canal,
        extra_structure_refs=extras,
    )
