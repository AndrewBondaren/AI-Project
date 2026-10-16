"""Resolve effective parallel worker counts from caller context + world caps."""

from __future__ import annotations

from app.application.jsonValidation import climate_scalars, terrain_scalars
from app.application.worldData.materializationContext import MaterializationContext
from app.db.models.world import World


def _resolve_workers(
    ctx: MaterializationContext,
    world_cap: int | None,
) -> int:
    workers = max(1, ctx.free_cores)
    if ctx.parallel_workers_override is not None:
        workers = min(workers, max(1, ctx.parallel_workers_override))
    if world_cap is not None and world_cap >= 1:
        workers = min(workers, world_cap)
    return max(1, workers)


def resolve_terrain_workers(ctx: MaterializationContext, world: World) -> int:
    cap = terrain_scalars(world).terrain_parallel_workers
    return _resolve_workers(ctx, cap)


def resolve_climate_workers(ctx: MaterializationContext, world: World) -> int:
    cap = climate_scalars(world).climate_parallel_workers
    return _resolve_workers(ctx, cap)
