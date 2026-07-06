"""World surface materialization facade — terrain (incl. hydrology) then climate.

Single entry for debug stack and future DAG materialization nodes.
See ``docs/tz_terrain_generation.md`` § materialization queue.
"""

from __future__ import annotations

import logging

from app.application.worldData.climateBatchOrchestrator import ClimateBatchOrchestrator
from app.application.worldData.generators.terrain.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.materializationContext import (
    MaterializationContext,
    MaterializationJobReport,
)
from app.application.worldData.parallelPolicy import (
    resolve_climate_workers,
    resolve_terrain_workers,
)
from app.application.worldData.terrainBatchOrchestrator import SurfaceMode, TerrainBatchOrchestrator
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


class WorldSurfaceMaterializationOrchestrator:
    """S→CL stack with shared ``MaterializationContext``."""

    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        climate: ClimateBatchOrchestrator,
    ) -> None:
        self._terrain = terrain
        self._climate = climate

    async def materialize_surface_stack(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        *,
        surface_mode: SurfaceMode = "bootstrap",
        max_tiles: int | None = 16,
        include_climate: bool = True,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
    ) -> MaterializationJobReport:
        terrain_workers = resolve_terrain_workers(ctx, world)
        climate_workers = resolve_climate_workers(ctx, world)

        terrain_res, chunks_done, chunks_total = await self._terrain.save_terrain_batch(
            world_uid,
            world,
            locations,
            ctx,
            nodes=nodes,
            edges=edges,
            hydrology_generator=hydrology_generator,
            surface_mode=surface_mode,
            max_tiles=max_tiles,
        )

        climate_res = None
        if include_climate and terrain_res.succeeded > 0:
            climate_res, _, _ = await self._climate.apply_climate_batch(
                world_uid, world, locations, ctx,
            )

        logger.info(
            "materialize_surface_stack | world=%s terrain=%d climate=%s chunks=%d/%d",
            world_uid,
            terrain_res.succeeded,
            climate_res.succeeded if climate_res else None,
            chunks_done,
            chunks_total,
        )
        return MaterializationJobReport(
            terrain=terrain_res,
            climate=climate_res,
            chunks_total=chunks_total,
            chunks_done=chunks_done,
            terrain_workers=terrain_workers,
            climate_workers=climate_workers,
        )
