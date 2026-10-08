"""Single-writer canal for ribbon seeds — R28/R36p/q.

Fit → knobs (+ registry). Not-fit → ``canal_obstacle_policy``.
Returns typed ``Canal | None``; unknown ref → shared unresolved.
"""

from __future__ import annotations

from collections.abc import Sequence
from app.application.jsonValidation.resolve import ResolveContext

from app.application.worldData.generators.terrain.relief.canal.attachments import (
    EVENT_CANAL_CUT_NO_CELLS,
    aggregate_canals,
    require_canal_from_registry_ref,
    normalize_structure_canal_ref,
)
from app.application.worldData.generators.terrain.relief.canal.obstacleResolve import (
    canal_entity_from_terrain,
    resolve_canal_obstacle_cut,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_warning
from app.dataModel.terrain.relief.canal import Canal, EarthenCanal
from app.dataModel.terrain.relief.canalObstaclePolicy import CanalObstaclePolicyRule
from app.dataModel.terrain.relief.worldCanalTemplateRegistry import (
    WorldCanalTemplateRegistry,
)

__all__ = [
    "aggregate_canals",
    "resolve_seed_canal",
]


def resolve_seed_canal(
    *,
    requested_length: int,
    L_eff: int,
    terrain_key: str,
    knobs_earthen: bool | None,
    knobs_structure_canal: str | None,
    policy_rules: Sequence[CanalObstaclePolicyRule],
    registry: WorldCanalTemplateRegistry,
    site_id: str,
    allow_cut_without_cells: bool = False,
    resolve_ctx: ResolveContext | None = None,
) -> Canal | None:
    """R36p/q: knobs if ``L_eff >= requested``; else world canal policy."""
    requested = max(0, int(requested_length))
    leff = max(0, int(L_eff))

    if leff >= requested:
        return _from_knobs(
            knobs_earthen=knobs_earthen,
            knobs_structure_canal=knobs_structure_canal,
            registry=registry,
            site_id=site_id,
            resolve_ctx=resolve_ctx,
        )

    entity = canal_entity_from_terrain(terrain_key)
    cut = resolve_canal_obstacle_cut(entity=entity, rules=policy_rules, resolve_ctx=resolve_ctx)
    if not cut.enable:
        return None

    if leff < 1 and not allow_cut_without_cells:
        relief_warning(
            EVENT_CANAL_CUT_NO_CELLS,
            site_id=site_id,
            terrain=terrain_key,
            canal_ref=cut.canal_ref,
            L_eff=leff,
            requested=requested,
        )
        return None

    if not cut.canal_ref:
        return EarthenCanal()

    return _resolve_canal_ref(
        cut.canal_ref,
        registry=registry,
        site_id=site_id,
        resolve_ctx=resolve_ctx,
    )


def _from_knobs(
    *,
    knobs_earthen: bool | None,
    knobs_structure_canal: str | None,
    registry: WorldCanalTemplateRegistry,
    site_id: str,
    resolve_ctx: ResolveContext | None = None,
) -> Canal | None:
    ref = normalize_structure_canal_ref(knobs_structure_canal)
    if ref is None:
        if knobs_earthen is True:
            return EarthenCanal()
        return None
    return _resolve_canal_ref(
        ref,
        registry=registry,
        site_id=site_id,
        resolve_ctx=resolve_ctx,
    )


def _resolve_canal_ref(
    canal_ref: str,
    *,
    registry: WorldCanalTemplateRegistry,
    site_id: str,
    resolve_ctx: ResolveContext | None = None,
) -> Canal:
    ctx = resolve_ctx if resolve_ctx is not None else ResolveContext(path_prefix=("canal", site_id))
    return require_canal_from_registry_ref(canal_ref, registry, resolve_ctx=ctx)
