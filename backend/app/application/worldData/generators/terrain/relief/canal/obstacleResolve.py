"""R36p: clearance-path canal cut from ``canal_obstacle_policy``."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.dataModel.terrain.relief.canalObstaclePolicy import CanalObstaclePolicyRule
from app.dataModel.terrain.relief.enums import (
    CanalObstacleEntity,
    ReliefConditionTerrain,
)


@dataclass(frozen=True, slots=True)
class CanalObstacleCut:
    """Result of matching world canal_obstacle_policy for one entity."""

    enable: bool
    canal_ref: str | None
    matched: int


# Overlap ReliefConditionTerrain ↔ CanalObstacleEntity (RELIEF-T-45 SoT map).
_TERRAIN_TO_CANAL_ENTITY: dict[str, CanalObstacleEntity] = {
    ReliefConditionTerrain.MOUNTAIN.value: CanalObstacleEntity.MOUNTAIN,
    ReliefConditionTerrain.PLAINS.value: CanalObstacleEntity.PLAINS,
    ReliefConditionTerrain.FOREST.value: CanalObstacleEntity.FOREST,
    ReliefConditionTerrain.SHORE_RIVER.value: CanalObstacleEntity.SHORE,
    ReliefConditionTerrain.SHORE_MOUNTAIN_RIVER.value: CanalObstacleEntity.SHORE,
    ReliefConditionTerrain.SHORE_LAKE.value: CanalObstacleEntity.SHORE,
    ReliefConditionTerrain.SHORE_SEA.value: CanalObstacleEntity.SHORE,
    "shore": CanalObstacleEntity.SHORE,
    CanalObstacleEntity.ROAD.value: CanalObstacleEntity.ROAD,
}


def canal_entity_from_terrain(terrain_key: str) -> CanalObstacleEntity | None:
    """Map segment / system_terrain → ``CanalObstacleEntity`` (or None)."""
    key = str(terrain_key or "").strip().lower()
    if not key:
        return None
    return _TERRAIN_TO_CANAL_ENTITY.get(key)


def resolve_canal_obstacle_cut(
    *,
    entity: CanalObstacleEntity | None,
    rules: Sequence[CanalObstaclePolicyRule],
) -> CanalObstacleCut:
    """Match rules; enable false wins; canal_ref must agree among true-rules."""
    if not rules:
        return CanalObstacleCut(enable=False, canal_ref=None, matched=0)

    matched: list[CanalObstaclePolicyRule] = []
    for rule in rules:
        entities = set(rule.entities)
        if CanalObstacleEntity.ALL in entities:
            matched.append(rule)
            continue
        if entity is not None and entity in entities:
            matched.append(rule)

    if not matched:
        return CanalObstacleCut(enable=False, canal_ref=None, matched=0)

    if any(not r.to_canal_cut_enable for r in matched):
        return CanalObstacleCut(enable=False, canal_ref=None, matched=len(matched))

    refs = {(r.canal_ref or "").strip() or None for r in matched}
    refs.discard(None)
    if len(refs) > 1:
        # Conflict — treat as disabled (validate should reject; runtime safe)
        return CanalObstacleCut(enable=False, canal_ref=None, matched=len(matched))
    canal_ref = next(iter(refs)) if refs else None
    return CanalObstacleCut(
        enable=True, canal_ref=canal_ref, matched=len(matched),
    )
