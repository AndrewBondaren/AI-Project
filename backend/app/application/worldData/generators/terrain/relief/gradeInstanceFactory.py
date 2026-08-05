"""Build ``ReliefGradeInstance`` after ribbon materialize — tz_terrain_relief §8c."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.application.worldData.generators.terrain.relief.volumeMaterialize import (
    RibbonVolumePlan,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance


def make_grade_uid(*, world_uid: str, site_id: str, seed: tuple[int, int]) -> str:
    """Deterministic uid for re-bake upsert."""
    key = f"{world_uid}|{site_id}|{seed[0]},{seed[1]}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return (
        f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-"
        f"{digest[16:20]}-{digest[20:32]}"
    )


def build_ribbon_grade_instance(
    *,
    world_uid: str,
    site_id: str,
    seed: tuple[int, int],
    plan: RibbonVolumePlan,
    cell_refs: tuple[tuple[int, int], ...],
    facing: str | None,
    earthen_canal: bool = False,
    template_uid: str | None = None,
    edge_uid: str | None = None,
) -> ReliefGradeInstance:
    """One Grade per successfully stamped seed strip (constant θ)."""
    if not cell_refs:
        raise ValueError("build_ribbon_grade_instance requires non-empty cell_refs")
    kind = plan.kind
    face = None if kind is ReliefSideKind.SHEER else facing
    if kind is ReliefSideKind.SHEER:
        face = None
    return ReliefGradeInstance(
        grade_uid=make_grade_uid(world_uid=world_uid, site_id=site_id, seed=seed),
        world_uid=world_uid,
        kind=kind,
        height_cells=plan.h,
        length_cells=plan.L,
        cell_refs=list(cell_refs),
        angle_deg=plan.angle_deg,
        facing=face,
        earthen_canal=earthen_canal,
        template_uid=template_uid,
        edge_uid=edge_uid,
        site_id=site_id,
        grade_system_uid=None,
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
