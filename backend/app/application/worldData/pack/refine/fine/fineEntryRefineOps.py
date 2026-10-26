"""L2 fine-terrain entry-time operations — scene/path volumes + queue scheduling.

Entry zone split out of the former ``FineTerrainRefineOrchestrator`` facade
(FM-5): synchronous scene/path refine passes and background enqueue helpers
used by ``EntryRefineOrchestrator``. Drain-time single-rect refine lives on
``FineRectRefiner``.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import (
    terrain_chunk_columns,
)
from app.application.worldData.materialize.shared.persistResult import PersistResult
from app.application.worldData.materialize.surface.materializationContext import MaterializationContext
from app.application.worldData.materialize.terrain.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_fine_terrain_phase_done,
    log_pack_fine_terrain_phase_start,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volumes_by_location,
)
from app.application.worldData.pack.read.packMapHelpers import tile_for_anchor
from app.application.worldData.pack.refine.chunks.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.refine.chunks.chunkSchedule import (
    schedule_path_ahead_tiles as schedule_path_ahead_tiles_fn,
    schedule_tile_background as schedule_tile_background_fn,
)
from app.application.worldData.pack.refine.entry.entryRingGeom import (
    chunk_within_ring,
    scene_chunk_indices as geom_scene_chunk_indices,
)
from app.application.worldData.pack.refine.fine.chunk.fineChunkGeom import (
    rects_for_macro_tile,
)
from app.application.worldData.pack.refine.fine.chunk.fineChunkRunner import FineChunkRunner
from app.application.worldData.pack.refine.fine.fineRefineGradePersist import (
    persist_refine_grade_instances,
)
from app.application.worldData.pack.refine.fine.fineRefineResult import FineRefineResult
from app.application.worldData.pack.refine.pathCorridorSelect import (
    select_path_corridor_rects,
)
from app.application.worldData.pack.refine.pathHeading import PathHeading
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from app.dataModel.worldPack.bake.gradePipelineStages import GradePipelineStages
from app.dataModel.worldPack.meta.worldPackManifest import ChunkRefineRole
from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository


class FineEntryRefineOps:
    """Entry-time L2 refine: scene/path synchronous passes + background scheduling."""

    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        runner: FineChunkRunner | None = None,
        relief_grade_repo: IReliefGradeRepository | None = None,
    ) -> None:
        self._runner = runner or FineChunkRunner(terrain)
        self._relief_grade_repo = relief_grade_repo

    async def refine_scene_volume(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        anchor_x: int,
        anchor_y: int,
        mat_ctx: MaterializationContext,
        *,
        surface_bundle: SurfacePlanBundle,
        tile_gx: int,
        tile_gy: int,
        xy_radius: int,
        location_volumes: list[TerritoryVolume] | None = None,
        region_state_snapshot: Mapping[str, StateSnapshotEntry],
        working: SurfaceWorkingMaps,
    ) -> tuple[PersistResult, int, int]:
        loc_volumes = location_volumes or [
            vol for _, vol in territory_volumes_by_location(world, locations)
        ]
        rects = rects_for_macro_tile(world, tile_gx, tile_gy)
        chunk_size = terrain_chunk_columns(world)
        scene_rects = [
            rect for rect in rects
            if chunk_within_ring(rect, float(anchor_x), float(anchor_y), float(xy_radius), chunk_size)
        ]
        phase_t0 = log_pack_fine_terrain_phase_start(
            world.world_uid,
            "scene",
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            rects=len(scene_rects),
        )
        result = await _run_refine_phase(
            self._runner, self._relief_grade_repo,
            world, locations, writer, mat_ctx, surface_bundle,
            tile_gx, tile_gy, scene_rects, loc_volumes,
            role="scene",
            phase="scene",
            started_at=phase_t0,
            region_state_snapshot=region_state_snapshot,
            working=working,
        )
        return result.persist, result.wilderness_chunks_written, result.rect_count

    async def refine_path_corridor(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        anchor_x: int,
        anchor_y: int,
        mat_ctx: MaterializationContext,
        surface_bundle: SurfacePlanBundle,
        tile_gx: int,
        tile_gy: int,
        *,
        heading: PathHeading | None = None,
        depth_tiles: int | None = None,
        region_state_snapshot: Mapping[str, StateSnapshotEntry],
        working: SurfaceWorkingMaps,
    ) -> int:
        """Refine coarse corridor ahead of anchor — PLAYER_PATH layer (MERGE-5 / DEBT-7)."""
        if heading is None or not heading.is_defined:
            return 0
        corridor = select_path_corridor_rects(
            world, tile_gx, tile_gy, anchor_x, anchor_y, heading,
            depth_tiles=depth_tiles,
        )
        if not corridor:
            return 0
        loc_volumes = [vol for _, vol in territory_volumes_by_location(world, locations)]
        phase_t0 = log_pack_fine_terrain_phase_start(
            world.world_uid,
            "path",
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            rects=len(corridor),
            heading=f"dx={heading.dx} dy={heading.dy}",
        )
        result = await _run_refine_phase(
            self._runner, self._relief_grade_repo,
            world, locations, writer, mat_ctx, surface_bundle,
            tile_gx, tile_gy, corridor, loc_volumes,
            role="path",
            phase="path",
            started_at=phase_t0,
            region_state_snapshot=region_state_snapshot,
            working=working,
        )
        return result.wilderness_chunks_written

    async def schedule_tile_background(
        self,
        world: World,
        queue: ChunkRefineQueue,
        anchor_x: int,
        anchor_y: int,
        tile_gx: int,
        tile_gy: int,
        *,
        skip_scene_rects: set[tuple[int, int]] | None = None,
        max_radius_fine: float | None = None,
    ) -> int:
        return await schedule_tile_background_fn(
            world, queue, anchor_x, anchor_y, tile_gx, tile_gy,
            skip_scene_rects=skip_scene_rects,
            max_radius_fine=max_radius_fine,
        )

    def scene_chunk_indices(
        self,
        world: World,
        tile_gx: int,
        tile_gy: int,
        anchor_x: int,
        anchor_y: int,
        *,
        xy_radius: int | None = None,
    ) -> set[tuple[int, int]]:
        """Chunk (cx,cy) indices covered by scene volume around anchor."""
        from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy

        radius = (
            xy_radius
            if xy_radius is not None
            else SceneVolumePolicy.canonical_defaults().scene_xy_radius
        )
        return geom_scene_chunk_indices(
            world, tile_gx, tile_gy, anchor_x, anchor_y, xy_radius=radius,
        )

    async def schedule_path_ahead_tiles(
        self,
        world: World,
        queue: ChunkRefineQueue,
        anchor_x: int,
        anchor_y: int,
        tile_gx: int,
        tile_gy: int,
        heading: PathHeading,
        *,
        depth_tiles: int,
    ) -> int:
        return await schedule_path_ahead_tiles_fn(
            world, queue, anchor_x, anchor_y, tile_gx, tile_gy, heading,
            depth_tiles=depth_tiles,
        )

    @staticmethod
    def tile_for_anchor(world: World, anchor_x: int, anchor_y: int) -> tuple[int, int]:
        return tile_for_anchor(world, anchor_x, anchor_y)


async def _run_refine_phase(
    runner: FineChunkRunner,
    relief_grade_repo: IReliefGradeRepository | None,
    world: World,
    locations: list[NamedLocation],
    writer: WorldPackWriter,
    mat_ctx: MaterializationContext,
    surface_bundle: SurfacePlanBundle,
    tile_gx: int,
    tile_gy: int,
    rects: list[ColumnRect],
    location_volumes: list[TerritoryVolume],
    *,
    role: ChunkRefineRole,
    phase: str,
    started_at: float,
    region_state_snapshot: Mapping[str, StateSnapshotEntry],
    working: SurfaceWorkingMaps,
) -> FineRefineResult:
    """One refine pass + grade persist + phase-done log (scene/path share it)."""
    result = await runner.refine_rects(
        world, locations, writer, mat_ctx, surface_bundle,
        tile_gx, tile_gy, rects, location_volumes,
        refine_role=role,
        phase=phase,
        stages=GradePipelineStages.off(),
        region_state_snapshot=region_state_snapshot,
        working=working,
    )
    await persist_refine_grade_instances(relief_grade_repo, world, result)
    log_pack_fine_terrain_phase_done(
        world.world_uid,
        phase,
        chunks_written=result.wilderness_chunks_written,
        cells_total=result.persist.succeeded,
        started_at=started_at,
        materialize_s=result.materialize_s,
        grade_s=result.grade_s,
    )
    return result
