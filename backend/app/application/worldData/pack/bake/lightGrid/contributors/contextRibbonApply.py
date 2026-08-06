"""Thin facade: sample_fn → ``apply_ribbon_grades`` for open_land / shore."""

from __future__ import annotations

from collections.abc import Callable

from app.application.jsonValidation import terrain_masks
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.ribbonGradeApply import (
    SampleCell,
    apply_ribbon_grades,
)
from app.application.worldData.pack.bake.lightGrid.ribbonIntent import (
    RibbonIntent,
)
from app.dataModel.terrain.relief.enums import ReliefContext

SampleFn = Callable[
    ...,
    tuple[list[SampleCell], set[tuple[int, int]]],
]


def apply_context_ribbon_grades(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    *,
    context: ReliefContext,
    sample_fn: SampleFn,
    occurrence_start: int = 0,
) -> list[RibbonIntent]:
    """Shared open_land / shore wire (BAR-1 runs once after full compose)."""
    if not ctx.relief_templates_by_uid:
        return []
    masks = terrain_masks(ctx.world)
    road_key = masks.default_roads.system_terrain
    tile_set = set(ctx.tiles)
    samples, ref_cells = sample_fn(
        compose, tile_set=tile_set, road_key=road_key,
    )
    return apply_ribbon_grades(
        compose,
        ctx,
        owner_uid=context.value,
        ref_cells=ref_cells,
        samples=samples,
        context=context,
        occurrence_start=occurrence_start,
    )
