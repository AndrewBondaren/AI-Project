"""Single-writer canal attachments for ribbon seeds — RELIEF-T-42/T-43/T-49.

Fit path → knobs (+ registry). Not-fit → ``canal_obstacle_policy`` (R36p).
Unknown registry ref → one R21 path (RELIEF-T-57).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.application.worldData.generators.terrain.relief.canalAttachments import (
    EMPTY_CANAL,
    EMPTY_EARTHEN_CUT,
    EVENT_CANAL_CUT_NO_CELLS,
    EVENT_R21_FALLBACK,
    FALLBACK_NO_CANAL,
    WHY_UNKNOWN_CANAL_REF,
    WHY_UNKNOWN_STRUCTURE_CANAL,
    CanalAttachments,
    aggregate_canal_attachments,
    attachments_from_registry_ref,
    no_canal_for_ref,
    normalize_structure_canal_ref,
)
from app.application.worldData.generators.terrain.relief.canalObstacleResolve import (
    canal_entity_from_terrain,
    resolve_canal_obstacle_cut,
)
from app.application.worldData.generators.terrain.relief.reliefLog import relief_warning
from app.dataModel.terrain.relief.canalObstaclePolicy import CanalObstaclePolicyRule
from app.dataModel.terrain.relief.worldCanalTemplateRegistry import (
    WorldCanalTemplateRegistry,
)

__all__ = [
    "CanalAttachments",
    "EMPTY_CANAL",
    "EMPTY_EARTHEN_CUT",
    "aggregate_canal_attachments",
    "resolve_seed_canal_attachments",
]


def resolve_seed_canal_attachments(
    *,
    requested_length: int,
    L_eff: int,
    terrain_key: str,
    knobs_earthen: bool | None,
    knobs_structure_canal: str | None,
    knobs_structure_refs: tuple[str, ...],
    policy_rules: Sequence[CanalObstaclePolicyRule],
    registry: WorldCanalTemplateRegistry,
    site_id: str,
    allow_cut_without_cells: bool = False,
) -> CanalAttachments:
    """R36p/q: knobs if ``L_eff >= requested``; else world canal policy.

    When not-fit and ``L_eff < 1`` (no cells): empty attachments + WARN unless
    ``allow_cut_without_cells`` (tests). Unknown registry refs → R21 empty + WARN.
    """
    requested = max(0, int(requested_length))
    leff = max(0, int(L_eff))

    if leff >= requested:
        return _from_knobs(
            knobs_earthen=knobs_earthen,
            knobs_structure_canal=knobs_structure_canal,
            knobs_structure_refs=knobs_structure_refs,
            registry=registry,
            site_id=site_id,
        )

    entity = canal_entity_from_terrain(terrain_key)
    cut = resolve_canal_obstacle_cut(entity=entity, rules=policy_rules)
    if not cut.enable:
        return EMPTY_CANAL

    if leff < 1 and not allow_cut_without_cells:
        relief_warning(
            EVENT_CANAL_CUT_NO_CELLS,
            site_id=site_id,
            terrain=terrain_key,
            canal_ref=cut.canal_ref,
            L_eff=leff,
            requested=requested,
        )
        return EMPTY_CANAL

    if not cut.canal_ref:
        return EMPTY_EARTHEN_CUT

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
    knobs_structure_refs: tuple[str, ...],
    registry: WorldCanalTemplateRegistry,
    site_id: str,
) -> CanalAttachments:
    ref = normalize_structure_canal_ref(knobs_structure_canal)
    if ref is None:
        return CanalAttachments(
            earthen_canal=bool(knobs_earthen),
            structure_refs=tuple(knobs_structure_refs),
            structure_canal=None,
        )
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
) -> CanalAttachments:
    """Single registry lookup + R21 fallback (knobs path and policy path)."""
    att = attachments_from_registry_ref(canal_ref, registry)
    if att is None:
        return _r21_no_canal(why=why, canal_ref=canal_ref, site_id=site_id)
    return att


def _r21_no_canal(
    *,
    why: str,
    canal_ref: str,
    site_id: str,
) -> CanalAttachments:
    relief_warning(
        EVENT_R21_FALLBACK,
        why=why,
        canal_ref=canal_ref,
        site_id=site_id,
        chosen_fallback=FALLBACK_NO_CANAL,
    )
    return no_canal_for_ref(canal_ref)
