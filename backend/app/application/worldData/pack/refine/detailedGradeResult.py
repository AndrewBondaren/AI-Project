"""Detailed-bake outdoor grade write-set — R36u / Post-R36w GradeFormation apply."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from app.application.worldData.generators.terrain.relief.log.log import relief_debug
from app.application.worldData.generators.terrain.relief.volume.volumeMaterialize import (
    RibbonVolumePlan,
)
from app.application.worldData.pack.refine.columnBounds import (
    ColumnBounds,
    rect_contains,
)
from app.application.worldData.pack.refine.meterGradeSurface import Coord
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.canal import Canal
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay, merge_grade_rim_rays
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance


@dataclass(frozen=True)
class DetailedGradeResult:
    """Uid + volume z overlay + instances for one rect (or merged rects).

    Overlay domain = uid domain. After merge/clip/``of``, ``reconciled()``
    enforces R36j: ``cell_refs`` = cells whose uid points at that instance.

    ``height_cells`` / ``length_cells`` are formation geom (R36j triangle), not
    ``len(cell_refs)``. Clip shrinks membership, not h/L.

    Raw constructor may be inconsistent (tests / ``reconciled`` internals).
    Public write-set: ``of`` / ``merged_with`` / ``clipped_to_rect`` / ``empty``.
    Do not mutate the dict fields after construction.
    """

    surface_grade_uid: dict[Coord, str] = field(default_factory=dict)
    surface_z: dict[Coord, int] = field(default_factory=dict)
    grade_instances: tuple[ReliefGradeInstance, ...] = ()
    rim_rays: tuple[GradeRimRay, ...] = ()

    @classmethod
    def empty(cls) -> DetailedGradeResult:
        return cls()

    @classmethod
    def of(
        cls,
        *,
        surface_grade_uid: Mapping[Coord, str] | None = None,
        surface_z: Mapping[Coord, int] | None = None,
        grade_instances: Iterable[ReliefGradeInstance] = (),
        rim_rays: Iterable[GradeRimRay] = (),
    ) -> DetailedGradeResult:
        """Public write-set: always R36j-reconciled."""
        return cls(
            surface_grade_uid=dict(surface_grade_uid or {}),
            surface_z=dict(surface_z or {}),
            grade_instances=tuple(grade_instances),
            rim_rays=tuple(rim_rays),
        ).reconciled()

    def reconciled(self) -> DetailedGradeResult:
        """Uid domain owns membership. Overlay ⊆ uid. Instances match uid (R36i-T-12)."""
        by_uid: dict[str, ReliefGradeInstance] = {}
        for inst in self.grade_instances:
            by_uid[inst.grade_uid] = inst
        cells_by_uid: dict[str, list[Coord]] = {}
        dropped_orphan: list[Coord] = []
        dropped_no_z: list[Coord] = []
        for xy in sorted(self.surface_grade_uid):
            uid = self.surface_grade_uid[xy]
            if uid not in by_uid:
                dropped_orphan.append(xy)
                continue
            if xy not in self.surface_z:
                dropped_no_z.append(xy)
                continue
            cells_by_uid.setdefault(uid, []).append(xy)
        if dropped_orphan or dropped_no_z:
            relief_debug(
                "grade_write_set_reconcile",
                dropped_orphan=tuple(dropped_orphan) or None,
                dropped_no_z=tuple(dropped_no_z) or None,
            )
        uids: dict[Coord, str] = {}
        overlay: dict[Coord, int] = {}
        instances: list[ReliefGradeInstance] = []
        for uid, inst in by_uid.items():
            refs = cells_by_uid.get(uid)
            if not refs:
                continue
            instances.append(inst.model_copy(update={"cell_refs": list(refs)}))
            for xy in refs:
                uids[xy] = uid
                overlay[xy] = self.surface_z[xy]
        return DetailedGradeResult(
            surface_grade_uid=uids,
            surface_z=overlay,
            grade_instances=tuple(instances),
            rim_rays=self.rim_rays,
        )

    def merged_with(self, other: DetailedGradeResult) -> DetailedGradeResult:
        """Uid/z last-wins; instance fields last-wins; membership from uid."""
        uids = dict(self.surface_grade_uid)
        uids.update(other.surface_grade_uid)
        overlay = dict(self.surface_z)
        overlay.update(other.surface_z)
        by_uid = {inst.grade_uid: inst for inst in self.grade_instances}
        by_uid.update({inst.grade_uid: inst for inst in other.grade_instances})
        return DetailedGradeResult(
            surface_grade_uid=uids,
            surface_z=overlay,
            grade_instances=tuple(by_uid.values()),
            rim_rays=merge_grade_rim_rays(self.rim_rays, other.rim_rays),
        ).reconciled()

    def clipped_to_rect(self, rect: ColumnBounds) -> DetailedGradeResult:
        """Uid ∩ rect; overlay ∩ those keys; ``cell_refs`` from remaining uid."""
        uids = {
            xy: uid
            for xy, uid in self.surface_grade_uid.items()
            if rect_contains(rect, xy[0], xy[1])
        }
        return DetailedGradeResult(
            surface_grade_uid=uids,
            surface_z={xy: z for xy, z in self.surface_z.items() if xy in uids},
            grade_instances=self.grade_instances,
            rim_rays=self.rim_rays,
        ).reconciled()


@dataclass(frozen=True, slots=True)
class GradeFormation:
    """Per-segment apply payload: overlay + corridor + entity plan + canal + uid.

    Overlay columns come from each seed's volume plan. Entity ``h/L/θ`` uses the
    longest seed plan (max ``plan.L``, first on tie) — not an incidental last seed.
    ``h/L`` stay on the instance after clip; membership is uid / ``cell_refs``.
    """

    plan: RibbonVolumePlan
    overlay: dict[Coord, int]
    corridor: tuple[Coord, ...]
    facing: Facing | None
    canal: Canal | None
    grade_uid: str

    def to_write_set(self, instance: ReliefGradeInstance) -> DetailedGradeResult:
        return DetailedGradeResult.of(
            surface_grade_uid={xy: self.grade_uid for xy in self.corridor},
            surface_z=self.overlay,
            grade_instances=(instance,),
        )
