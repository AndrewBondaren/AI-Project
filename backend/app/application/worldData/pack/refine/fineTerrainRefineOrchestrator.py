"""L2 fine-terrain refine facade — WP-13 scene / path / queued chunk.

Delegates generate+persist to ``FineChunkRunner``, enqueue to ``chunkSchedule``,
corridor select to ``pathCorridorSelect``. Public method names stable for
``EntryRefineOrchestrator`` / ``ChunkRefineWorker``.
"""

from __future__ import annotations

from app.application.worldData.materialize.persistResult import PersistResult
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import (
    terrain_chunk_columns,
)
from app.application.worldData.materialize.materializationContext import MaterializationContext
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_fine_terrain_phase_done,
    log_pack_fine_terrain_phase_start,
)
from app.application.worldData.pack.refine.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.refine.chunkSchedule import (
    schedule_path_ahead_tiles as schedule_path_ahead_tiles_fn,
    schedule_tile_background as schedule_tile_background_fn,
)
from app.application.worldData.pack.refine.entryRingGeom import (
    chunk_within_ring,
    scene_chunk_indices as geom_scene_chunk_indices,
)
from app.application.worldData.pack.refine.fineChunkRunner import FineChunkRunner
from app.application.worldData.pack.refine.fineRefineResult import FineRefineResult
from app.application.worldData.persist.persistReliefGrades import persist_relief_grades
from app.application.worldData.pack.refine.pathCorridorSelect import (
    select_path_corridor_rects,
)
from app.application.worldData.pack.refine.pathHeading import PathHeading
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volumes_by_location,
)
from app.application.worldData.pack.read.packMapHelpers import tile_for_anchor
from app.application.worldData.pack.refine.fineChunkGeom import (
    fine_chunk_rect,
    rects_for_macro_tile,
)
from app.application.templateLibrary.templateSnapshotLoader import TemplateSnapshotLoader
from app.application.worldData.materialize.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.worldPack.gradePipelineStages import GradePipelineStages
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository


class FineTerrainRefineOrchestrator:
    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        runner: FineChunkRunner | None = None,
        relief_loader: TemplateSnapshotLoader | None = None,
        relief_grade_repo: IReliefGradeRepository | None = None,
    ) -> None:
        self._terrain = terrain
        self._runner = runner or FineChunkRunner(terrain)
        self._relief_loader = relief_loader
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
        surface_ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        xy_radius: int,
        location_volumes: list[TerritoryVolume] | None = None,
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
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, scene_rects, loc_volumes,
            role="scene",
            phase="scene",
            started_at=phase_t0,
        )
        return result.persist, result.wilderness_chunks_written, result.rect_count

    async def refine_rect(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        rect: ColumnRect,
        location_volumes: list[TerritoryVolume] | None = None,
        *,
        refine_role: ChunkRefineRole = "background",
        stages: GradePipelineStages | None = None,
    ) -> FineRefineResult:
        loc_volumes = location_volumes or [
            vol for _, vol in territory_volumes_by_location(world, locations)
        ]
        resolved = stages or GradePipelineStages.off()
        templates = await self._relief_templates(world) if resolved.mill else None
        result = await self._runner.refine_rects(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, [rect], loc_volumes,
            refine_role=refine_role,
            phase=refine_role,
            relief_templates_by_uid=templates,
            stages=resolved,
        )
        await _persist_grade_instances(self._relief_grade_repo, world, result)
        return result

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
        max_radius_m: float | None = None,
    ) -> int:
        return await schedule_tile_background_fn(
            world, queue, anchor_x, anchor_y, tile_gx, tile_gy,
            skip_scene_rects=skip_scene_rects,
            max_radius_m=max_radius_m,
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

    async def refine_queued_chunk(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        cx: int,
        cy: int,
        *,
        stages: GradePipelineStages | None = None,
    ) -> FineRefineResult:
        rect = fine_chunk_rect(world, tile_gx, tile_gy, cx, cy)
        return await self.refine_rect(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, rect,
            refine_role="background",
            stages=stages,
        )

    async def refine_path_corridor(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        anchor_x: int,
        anchor_y: int,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        *,
        heading: PathHeading | None = None,
        depth_tiles: int | None = None,
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
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, corridor, loc_volumes,
            role="path",
            phase="path",
            started_at=phase_t0,
        )
        return result.wilderness_chunks_written

    async def _relief_templates(self, world: World) -> dict[str, ReliefTemplate]:
        """Fresh membership snapshot per refine job — same boundary as
        pack/detailed bake: member attach/detach/replace between jobs is
        visible to the next job; nothing is cached across operations."""
        out: dict[str, ReliefTemplate] = {}
        if self._relief_loader is not None:
            from app.application.templateLibrary.loadReliefTemplatesForWorld import (
                load_relief_templates_for_world,
            )

            out = await load_relief_templates_for_world(self._relief_loader, world)
        return out

    @staticmethod
    def tile_for_anchor(world: World, anchor_x: int, anchor_y: int) -> tuple[int, int]:
        return tile_for_anchor(world, anchor_x, anchor_y)

    # Compat for tests that called private _refine_rects
    async def _refine_rects(self, *args, **kwargs):
        return await self._runner.refine_rects(*args, **kwargs)


async def _persist_grade_instances(
    relief_grade_repo: IReliefGradeRepository | None,
    world: World,
    result: FineRefineResult,
) -> None:
    if relief_grade_repo is None or not result.grade_instances:
        return
    await persist_relief_grades(
        relief_grade_repo,
        world_uid=world.world_uid,
        instances=list(result.grade_instances),
        systems=list(result.grade_systems),
        replace_world=False,
    )


async def _run_refine_phase(
    runner: FineChunkRunner,
    relief_grade_repo: IReliefGradeRepository | None,
    world: World,
    locations: list[NamedLocation],
    writer: WorldPackWriter,
    mat_ctx: MaterializationContext,
    surface_ctx: SurfaceTerrainContext,
    tile_gx: int,
    tile_gy: int,
    rects: list[ColumnRect],
    location_volumes: list[TerritoryVolume],
    *,
    role: ChunkRefineRole,
    phase: str,
    started_at: float,
) -> FineRefineResult:
    """One refine pass + grade persist + phase-done log (scene/path share it)."""
    result = await runner.refine_rects(
        world, locations, writer, mat_ctx, surface_ctx,
        tile_gx, tile_gy, rects, location_volumes,
        refine_role=role,
        phase=phase,
        stages=GradePipelineStages.off(),
    )
    await _persist_grade_instances(relief_grade_repo, world, result)
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
