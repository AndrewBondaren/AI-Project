"""MaskDomainMaterializer protocol + runner — tz_map_light_bake § MaskDomain materialize.

Not the DAG ``application/engine`` — L0 mask Spec lifecycle only.

Spec sources (merge order): ``load_declared`` > ``load_anchor_specs`` > ``autoresolve_specs``.
Anchors (e.g. geographic named) are **not** declare — see tz § Declare / Q2.
"""

from __future__ import annotations

import logging
from typing import Protocol, TypeVar

from app.application.jsonValidation import terrain_masks as read_terrain_masks
from app.application.worldData.masks.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import MaskFootprint
from app.application.worldData.masks.mergeDeclare import merge_declare_over_auto
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.masks.enums.maskDomainId import MaskDomainId
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks

logger = logging.getLogger(__name__)

SpecT = TypeVar("SpecT")


class MaskDomainMaterializer(Protocol[SpecT]):
    """Per-domain mask materialize plugin. SpecT is domain-specific (not a shared blob)."""

    domain: MaskDomainId

    def begin_pass(self) -> None:
        """Reset per-bake-pass state (anti-stack, caches). Required; no-op if unused."""
        ...

    def load_declared(self, ctx: LightGridBakeContext) -> list[SpecT]:
        """Wire ``declared_*[]`` only — not geographic / named anchors."""
        ...

    def load_anchor_specs(self, ctx: LightGridBakeContext) -> list[SpecT]:
        """Optional named/geographic anchors → Spec. Not declare-path. Empty if none."""
        ...

    def autoresolve_specs(
        self,
        ctx: LightGridBakeContext,
        policy: MaskCategoryPolicy,
    ) -> list[SpecT]: ...

    def collect(
        self,
        ctx: LightGridBakeContext,
        policy: MaskCategoryPolicy,
    ) -> list[SpecT]:
        """Merge sources — prefer ``default_collect``; do not inline placement."""
        ...

    def materialize(self, spec: SpecT, scale: LightGridScale) -> MaskFootprint: ...

    def apply(
        self,
        compose: LightGridCompose,
        footprint: MaskFootprint,
        spec: SpecT,
        masks: WorldTerrainMasks,
        *,
        tile_set: set[tuple[int, int]],
        ctx: LightGridBakeContext,
    ) -> None: ...

    def category_policy(self, masks: WorldTerrainMasks) -> MaskCategoryPolicy: ...


def default_collect(
    materializer: MaskDomainMaterializer[SpecT],
    ctx: LightGridBakeContext,
    policy: MaskCategoryPolicy,
    *,
    key,
) -> list[SpecT]:
    """Merge order: declared > anchors > autoresolve."""
    declared = materializer.load_declared(ctx)
    anchors = materializer.load_anchor_specs(ctx)
    base = merge_declare_over_auto(declared, anchors, key=key)
    if not bool(policy.autoresolve):
        return base
    auto = materializer.autoresolve_specs(ctx, policy)
    return merge_declare_over_auto(base, auto, key=key)


def run_mask_domain(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    materializer: MaskDomainMaterializer[SpecT],
    masks: WorldTerrainMasks | None = None,
) -> int:
    """Gate → begin_pass → collect → materialize → apply. Returns specs applied."""
    masks = masks if masks is not None else read_terrain_masks(ctx.world)
    policy = materializer.category_policy(masks)
    if not masks.category_enabled(policy):
        logger.debug(
            "run_mask_domain | world=%s domain=%s skipped=disabled",
            ctx.world.world_uid,
            materializer.domain.value,
        )
        return 0
    materializer.begin_pass()
    specs = materializer.collect(ctx, policy)
    tile_set = set(ctx.tiles)
    for spec in specs:
        footprint = materializer.materialize(spec, compose.scale)
        if not footprint.cells:
            continue
        materializer.apply(compose, footprint, spec, masks, tile_set=tile_set, ctx=ctx)
    logger.debug(
        "run_mask_domain | world=%s domain=%s specs=%d",
        ctx.world.world_uid,
        materializer.domain.value,
        len(specs),
    )
    return len(specs)


__all__ = [
    "MaskDomainMaterializer",
    "apply_terrain_footprint",
    "default_collect",
    "run_mask_domain",
]
