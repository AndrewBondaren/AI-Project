"""World pack materialization facade — thin entry for debug HTTP / scripts.

Legacy map_cells ``materialize_surface_stack`` removed; use pack bake modes.
"""

from __future__ import annotations

from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    require_surface_terrain_context,
)
from app.application.worldData.pack.bake.packDetailedBakeOrchestrator import (
    PackDetailedBakeOrchestrator,
)
from app.application.worldData.pack.bake.packMaterializationOrchestrator import (
    PackMaterializationOrchestrator,
)
from app.application.worldData.materializationContext import (
    MaterializationContext,
    MaterializationJobReport,
)
from app.application.worldData.persistResult import PersistResult
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class WorldSurfaceMaterializationOrchestrator:
    """Pack surface materialization entry — light / full / detailed."""

    def __init__(
        self,
        pack: PackMaterializationOrchestrator,
        *,
        detailed: PackDetailedBakeOrchestrator | None = None,
    ) -> None:
        self._pack = pack
        self._detailed = detailed or PackDetailedBakeOrchestrator(pack.terrain)

    async def materialize_pack_light(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        *,
        max_tiles: int | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
        heading_dx: int | None = None,
        heading_dy: int | None = None,
        pack_orchestrator: PackMaterializationOrchestrator | None = None,
    ) -> MaterializationJobReport:
        orch = pack_orchestrator if pack_orchestrator is not None else self._pack
        return await orch.materialize_light_pack(
            world_uid, world, locations, pack_writer, ctx,
            max_tiles=max_tiles,
            nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
            anchor_x=anchor_x, anchor_y=anchor_y,
            heading_dx=heading_dx, heading_dy=heading_dy,
        )

    async def materialize_pack_full(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        refine_scene: bool | None = None,
    ) -> MaterializationJobReport:
        return await self._pack.materialize_full_pack(
            world_uid, world, locations, pack_writer, ctx,
            nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
            refine_scene=refine_scene,
        )

    async def materialize_pack_detailed(
        self,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        location_uid: str,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
    ) -> PersistResult:
        surface_ctx = require_surface_terrain_context(
            world, locations, nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
        )
        return await self._detailed.bake_location(
            world, locations, pack_writer, ctx, surface_ctx, location_uid,
        )
