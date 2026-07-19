"""Pack L0 materialization — light_bake / full_bake share one body (WP-27)."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.application.worldData.persistResult import PersistResult
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    require_surface_terrain_context,
)
from app.application.worldData.materializationContext import (
    MaterializationContext,
    MaterializationJobReport,
)
from app.application.worldData.pack.climate.climatePackBakeOrchestrator import ClimatePackBakeOrchestrator
from app.application.worldData.pack.bake.worldMapBakeOrchestrator import WorldMapBakeOrchestrator
from app.application.worldData.pack.refine.entryRefineOrchestrator import EntryRefineOrchestrator
from app.application.worldData.pack.refine.fineTerrainRefineOrchestrator import FineTerrainRefineOrchestrator
from app.application.worldData.pack.bake.locationsIndexBake import build_locations_index
from app.application.worldData.pack.bake.packBakeFinalize import finalize_pack_on_world
from app.application.worldData.pack.bake.packTilePlanner import PackTilePlanner
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.parallelPolicy import resolve_terrain_workers
from app.core.generationLogging import generation_world_log
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults
from app.dataModel.worldPack.packBakeMode import PackBakeMode
from app.dataModel.worldPack.packTilePlan import PackTilePlanScope
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.application.worldData.worldService import WorldService
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iChunkRefineJobRepository import IChunkRefineJobRepository
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_bake_done,
    log_pack_bake_start,
)


class PackMaterializationOrchestrator:
    """L0 world_map / climate coarse bake. Entry refine on ``EntryRefineOrchestrator``."""

    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        world_map: WorldMapBakeOrchestrator | None = None,
        fine_terrain: FineTerrainRefineOrchestrator | None = None,
        entry: EntryRefineOrchestrator | None = None,
        job_repo: IChunkRefineJobRepository | None = None,
        world_service: WorldService | None = None,
        bake_defaults: PackBakeDefaults | None = None,
        read_context: PackReadContext | None = None,
        read_context_for: Callable[[str], PackReadContext] | None = None,
        climate_bake: ClimatePackBakeOrchestrator | None = None,
        tile_planner: PackTilePlanner | None = None,
    ) -> None:
        self._terrain = terrain
        self._world_map = world_map or WorldMapBakeOrchestrator()
        self._defaults = bake_defaults or PackBakeDefaults.canonical_defaults()
        self._planner = tile_planner or PackTilePlanner(bake_defaults=self._defaults)
        self._world_service = world_service
        self._read_context = read_context
        self._read_context_for = read_context_for
        if entry is not None:
            self._entry = entry
            self._climate = climate_bake or entry.climate_bake
        else:
            self._climate = climate_bake or ClimatePackBakeOrchestrator(
                read_context=read_context,
                bake_defaults=self._defaults,
            )
            fine = fine_terrain or FineTerrainRefineOrchestrator(terrain)
            self._entry = EntryRefineOrchestrator(
                fine,
                job_repo=job_repo,
                bake_defaults=self._defaults,
                climate_bake=self._climate,
                read_context=read_context,
            )

    @property
    def terrain(self) -> TerrainBatchOrchestrator:
        return self._terrain

    @property
    def entry(self) -> EntryRefineOrchestrator:
        return self._entry

    @property
    def tile_planner(self) -> PackTilePlanner:
        return self._planner

    async def materialize_light_pack(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        *,
        max_tiles: int | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
        heading_dx: int | None = None,
        heading_dy: int | None = None,
        refine_scene: bool | None = None,
    ) -> MaterializationJobReport:
        with generation_world_log(world_uid, mode="light"):
            return await self._materialize_l0_pack(
                world_uid,
                world,
                locations,
                writer,
                mat_ctx,
                scope="light",
                max_tiles=max_tiles,
                nodes=nodes,
                edges=edges,
                hydrology_generator=hydrology_generator,
                anchor_x=anchor_x,
                anchor_y=anchor_y,
                heading_dx=heading_dx,
                heading_dy=heading_dy,
                refine_scene=(
                    self._defaults.refine_scene_on_light
                    if refine_scene is None
                    else refine_scene
                ),
            )

    async def materialize_full_pack(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        refine_scene: bool | None = None,
    ) -> MaterializationJobReport:
        """full_bake — same L0 pipeline, all macro-tiles in world_bounds / resolved AABB."""
        with generation_world_log(world_uid, mode="full"):
            return await self._materialize_l0_pack(
                world_uid,
                world,
                locations,
                writer,
                mat_ctx,
                scope="full",
                max_tiles=None,
                nodes=nodes,
                edges=edges,
                hydrology_generator=hydrology_generator,
                refine_scene=(
                    self._defaults.refine_scene_on_full
                    if refine_scene is None
                    else refine_scene
                ),
            )

    async def _materialize_l0_pack(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        *,
        scope: PackTilePlanScope,
        max_tiles: int | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
        heading_dx: int | None = None,
        heading_dy: int | None = None,
        refine_scene: bool = True,
    ) -> MaterializationJobReport:
        surface_ctx = require_surface_terrain_context(
            world, locations, nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
        )
        plan = self._planner.plan(
            world, locations, surface_ctx, scope=scope, max_tiles=max_tiles,
        )
        tiles = plan.tile_tuples()
        bake_mode: PackBakeMode = "full" if scope == "full" else "light"
        bake_t0 = log_pack_bake_start(
            world_uid,
            tile_cap=plan.cap_applied if plan.cap_applied is not None else -1,
            tiles_planned=len(tiles),
            refine_scene=refine_scene,
            locations=len(locations),
            terrain_workers=resolve_terrain_workers(mat_ctx, world),
        )
        drain = self._defaults.background_drain_per_request
        if self._entry.has_job_repo and drain > 0:
            await self._entry.drain_persisted(
                world_uid, world, locations, writer, mat_ctx, surface_ctx,
                max_jobs=drain,
            )

        climate_result: PersistResult | None = None
        climate_coarse_samples = 0
        climate_fine_tiles = 0
        climate_result, climate_coarse_samples = self._climate.bake_coarse(
            world, surface_ctx, writer, locations=locations,
        )

        locations_index = build_locations_index(locations)
        writer.write_locations_index(locations_index)

        # Incremental: still bake all planned tiles (overwrite) so content stays consistent
        world_map_cells = self._world_map.bake_tiles(
            world, locations, writer, tiles,
            surface_ctx=surface_ctx,
            locations_index=locations_index,
            nodes=nodes, edges=edges, hydrology_generator=hydrology_generator,
            bake_mode=bake_mode,
        )
        terrain_result = PersistResult.from_counts(world_map_cells, world_map_cells)
        chunks_done = 0
        chunks_total = 0

        climate_fine_tiles = self._climate.bake_fine_for_l0_policy(
            world, surface_ctx, writer, tiles, locations,
            scope=scope,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
        )
        if climate_fine_tiles and climate_result is not None:
            climate_result = PersistResult.from_counts(
                climate_result.total + climate_fine_tiles,
                climate_result.succeeded + climate_fine_tiles,
            )
        elif climate_fine_tiles:
            climate_result = PersistResult.from_counts(climate_fine_tiles, climate_fine_tiles)

        if refine_scene and tiles:
            ax = anchor_x
            ay = anchor_y
            if ax is None or ay is None:
                for loc in locations:
                    if loc.map_x is not None and loc.map_y is not None:
                        ax = loc.map_x
                        ay = loc.map_y
                        break
            if ax is None or ay is None:
                raise ValueError(
                    "pack L0 bake refine requires anchor_x/anchor_y "
                    "or a location with map_x/map_y",
                )
            entry = await self._entry.refine_from_entry(
                world_uid, world, locations, writer, mat_ctx, surface_ctx,
                kind="session_start",
                anchor_x=ax,
                anchor_y=ay,
                heading_dx=heading_dx,
                heading_dy=heading_dy,
            )
            scheduled = await self._entry.schedule_chunk_refine(
                world_uid, world, locations, writer, mat_ctx, surface_ctx,
                anchor_x=ax,
                anchor_y=ay,
                tile_gx=entry.tile_gx,
                tile_gy=entry.tile_gy,
                heading=entry.heading,
            )
            terrain_result = entry.terrain
            chunks_done = entry.chunks_done
            chunks_total = entry.chunks_total
            # Legacy drain may still bake fine if something else enqueued.
            extra_fine = scheduled.climate_fine_tiles
            if extra_fine:
                climate_fine_tiles += extra_fine
                if climate_result is not None:
                    climate_result = PersistResult.from_counts(
                        climate_result.total + extra_fine,
                        climate_result.succeeded + extra_fine,
                    )
                else:
                    climate_result = PersistResult.from_counts(extra_fine, extra_fine)

        if self._world_service is not None:
            read_ctx = self._read_context
            if read_ctx is None and self._read_context_for is not None:
                read_ctx = self._read_context_for(world_uid)
            await finalize_pack_on_world(
                self._world_service,
                world,
                writer,
                read_context=read_ctx,
            )

        workers = resolve_terrain_workers(mat_ctx, world)
        elapsed_s = time.perf_counter() - bake_t0
        queue_depth = len(self._entry.refine_queue)
        log_pack_bake_done(
            world_uid,
            world_map_cells=world_map_cells,
            chunks_done=chunks_done,
            chunks_total=chunks_total,
            queue_depth=queue_depth,
            started_at=bake_t0,
        )
        return MaterializationJobReport(
            terrain=terrain_result,
            climate=climate_result,
            chunks_done=chunks_done,
            chunks_total=chunks_total,
            terrain_workers=workers,
            climate_workers=0,
            elapsed_s=elapsed_s,
            world_map_cells=world_map_cells,
            refine_queue_depth=queue_depth,
            climate_coarse_samples=climate_coarse_samples or None,
            climate_fine_tiles=climate_fine_tiles or None,
        )
