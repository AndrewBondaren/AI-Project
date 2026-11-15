"""R36t canal-cut on a volume corridor — instance fields, not a voxel ditch."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.pick.ribbonGrade import RibbonGradeResult
from app.application.worldData.generators.terrain.relief.canal.seedResolve import (
    resolve_seed_canal,
)
from app.dataModel.terrain.relief.canal import Canal
from app.dataModel.terrain.relief.canalObstaclePolicy import CanalObstaclePolicyRule
from app.dataModel.terrain.relief.worldCanalTemplateRegistry import WorldCanalTemplateRegistry


def r36t_include_cut_end(
    *,
    canal: Canal | None,
    L_eff: int,
    requested: int,
) -> bool:
    """Shortened-end ref may join the uid/z domain when canal is on (R36t)."""
    return canal is not None and L_eff < requested


def canal_for_seed(
    result: RibbonGradeResult,
    *,
    requested: int,
    L_eff: int,
    policy_rules: tuple[CanalObstaclePolicyRule, ...],
    registry: WorldCanalTemplateRegistry,
) -> Canal | None:
    """Resolve canal from caller registry — no silent ``canonical_defaults()``."""
    return resolve_seed_canal(
        requested_length=requested,
        L_eff=L_eff,
        terrain_key=result.segment.terrain_key,
        knobs_earthen=result.decision.earthen_canal,
        knobs_structure_canal=result.decision.structure_canal,
        policy_rules=policy_rules,
        registry=registry,
        site_id=result.segment.site_id,
    )
