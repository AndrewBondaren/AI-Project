"""Single-writer canal for ribbon seeds — R28/R36p/q.

Fit → knobs (+ registry). Not-fit → ``canal_obstacle_policy``.
Returns typed ``Canal | None``; unknown ref → one R21 path.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.application.worldData.generators.terrain.relief.canal.attachments import (
    EVENT_CANAL_CUT_NO_CELLS,
    EVENT_RESOLVE_FALLBACK,
    FALLBACK_NO_CANAL,
    WHY_UNKNOWN_CANAL_REF,
    WHY_UNKNOWN_STRUCTURE_CANAL,
    aggregate_canals,
    canal_from_registry_ref,
    normalize_structure_canal_ref,
)
from app.application.worldData.generators.terrain.relief.canal.obstacleResolve import (
    canal_entity_from_terrain,
    resolve_canal_obstacle_cut,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_warning
from app.dataModel.terrain.relief.canal import Canal, EarthenCanal, StructureCanal
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
        )

    entity = canal_entity_from_terrain(terrain_key)
    cut = resolve_canal_obstacle_cut(entity=entity, rules=policy_rules)
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
        why=WHY_UNKNOWN_CANAL_REF,
    )


def _from_knobs(
    *,
    knobs_earthen: bool | None,
    knobs_structure_canal: str | None,
    registry: WorldCanalTemplateRegistry,
    site_id: str,
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
        why=WHY_UNKNOWN_STRUCTURE_CANAL,
    )


def _resolve_canal_ref(
    canal_ref: str,
    *,
    registry: WorldCanalTemplateRegistry,
    site_id: str,
    why: str,
) -> Canal | None:
    found = canal_from_registry_ref(canal_ref, registry)
    if found is None:
        return _r21_unknown(why=why, canal_ref=canal_ref, site_id=site_id)
    return found


def _r21_unknown(
    *,
    why: str,
    canal_ref: str,
    site_id: str,
) -> StructureCanal:
    relief_warning(
        EVENT_RESOLVE_FALLBACK,
        why=why,
        canal_ref=canal_ref,
        site_id=site_id,
        chosen_fallback=FALLBACK_NO_CANAL,
    )
    return StructureCanal(system_type=canal_ref, structure_refs=[])
