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
from app.application.worldData.pack.bake.packBakeResult import PackBakeResult
from app.application.worldData.pack.bake.packDetailedBakeOrchestrator import (
    PackDetailedBakeOrchestrator,
    PackDetailedBakeResult,
)
from app.application.worldData.pack.bake.packMaterializationOrchestrator import (
    PackMaterializationOrchestrator,
)
from app.application.worldData.materializationContext import (
    MaterializationContext,
    MaterializationJobReport,
)
from app.dataModel.worldPack.detailedBakeScope import (
    DetailedBakeRequest,
    DetailedBakeScopeKind,
    resolve_detailed_bake_request,
)
from app.dataModel.worldPack.packBakeMode import PackBakeApiMode
from app.dataModel.worldPack.packTilePlan import PackTilePlanScope
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

    async def bake_pack(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        *,
        mode: PackBakeApiMode,
        max_tiles: int | None = None,
        location_uid: str | None = None,
        detailed_scope: DetailedBakeScopeKind | None = None,
        detailed_request: DetailedBakeRequest | None = None,
        tile_gx: int | None = None,
        tile_gy: int | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
    ) -> PackBakeResult:
        """Single application entry for HTTP ``mode=light|full|detailed``.

        L0 only for light/full (Job boundaries). Entry/L2 → refine-from-entry
        or ``mode=detailed`` with typed scope / ``DetailedBakeRequest``.
        """
        if mode == "light":
            report = await self.materialize_pack_light(
                world_uid, world, locations, ctx, pack_writer,
                max_tiles=max_tiles,
                nodes=nodes, edges=edges,
                hydrology_generator=hydrology_generator,
                anchor_x=anchor_x, anchor_y=anchor_y,
            )
            return PackBakeResult(
                mode=mode,
                terrain_failed=report.terrain.failed,
                report=report,
            )
        if mode == "full":
            report = await self.materialize_pack_full(
                world_uid, world, locations, ctx, pack_writer,
                nodes=nodes, edges=edges,
                hydrology_generator=hydrology_generator,
            )
            return PackBakeResult(
                mode=mode,
                terrain_failed=report.terrain.failed,
                report=report,
            )
        if mode == "detailed":
            request = detailed_request or resolve_detailed_bake_request(
                scope=detailed_scope,
                location_uid=location_uid,
                max_tiles=max_tiles or 0,
                tile_gx=tile_gx,
                tile_gy=tile_gy,
            )
            detailed = await self.materialize_pack_detailed(
                world, locations, ctx, pack_writer, request,
                nodes=nodes, edges=edges,
                hydrology_generator=hydrology_generator,
            )
            return PackBakeResult(
                mode=mode,
                terrain_failed=detailed.terrain.failed,
                detailed=detailed,
                climate_fine_tiles=detailed.climate_fine_tiles or None,
            )
        raise ValueError(f"unknown pack bake mode '{mode}'")

    def plan_bootstrap_tiles(
        self,
        world: World,
        locations: list[NamedLocation],
        *,
        scope: PackTilePlanScope = "light",
        max_tiles: int | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
    ):
        """Preview L0 tile set — application owns surface_ctx + planner."""
        surface_ctx = require_surface_terrain_context(
            world, locations, nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
        )
        return self._pack.tile_planner.plan(
            world, locations, surface_ctx,
            scope=scope,
            max_tiles=max_tiles if scope == "light" else None,
        )

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
        pack_orchestrator: PackMaterializationOrchestrator | None = None,
    ) -> MaterializationJobReport:
        orch = pack_orchestrator if pack_orchestrator is not None else self._pack
        return await orch.materialize_light_pack(
            world_uid, world, locations, pack_writer, ctx,
            max_tiles=max_tiles,
            nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
            anchor_x=anchor_x, anchor_y=anchor_y,
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
    ) -> MaterializationJobReport:
        return await self._pack.materialize_full_pack(
            world_uid, world, locations, pack_writer, ctx,
            nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
        )

    async def materialize_pack_detailed(
        self,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        request: DetailedBakeRequest,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
    ) -> PackDetailedBakeResult:
        surface_ctx = require_surface_terrain_context(
            world, locations, nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
        )
        return await self._detailed.bake(
            world, locations, pack_writer, ctx, surface_ctx, request,
        )
