"""L2 fine-terrain drain-time refine — standalone/queued single-rect operations.

Drain zone split out of the former ``FineTerrainRefineOrchestrator`` facade
(FM-5): nested queued work does not publish; the public ``refine_rect`` commits
the manifest itself. Entry-time scene/path/schedule lives on
``FineEntryRefineOps``.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.application.templateLibrary.templateSnapshotLoader import TemplateSnapshotLoader
from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.materialize.surface.materializationContext import MaterializationContext
from app.application.worldData.materialize.terrain.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volumes_by_location,
)
from app.application.worldData.pack.refine.fine.chunk.fineChunkGeom import (
    fine_chunk_rect,
)
from app.application.worldData.pack.refine.fine.chunk.fineChunkRunner import FineChunkRunner
from app.application.worldData.pack.refine.fine.fineRefineGradePersist import (
    persist_refine_grade_instances,
)
from app.application.worldData.pack.refine.fine.fineRefineResult import FineRefineResult
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.worldPack.bake.gradePipelineStages import GradePipelineStages
from app.dataModel.worldPack.meta.worldPackManifest import ChunkRefineRole
from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository


class FineRectRefiner:
    """Drain-time L2 refine: standalone/queued single-rect operations."""

    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        runner: FineChunkRunner | None = None,
        relief_loader: TemplateSnapshotLoader | None = None,
        relief_grade_repo: IReliefGradeRepository | None = None,
    ) -> None:
        self._runner = runner or FineChunkRunner(terrain)
        self._relief_loader = relief_loader
        self._relief_grade_repo = relief_grade_repo

    async def refine_rect(
        self, world: World, locations: list[NamedLocation], writer: WorldPackWriter,
        mat_ctx: MaterializationContext, surface_bundle: SurfacePlanBundle,
        tile_gx: int, tile_gy: int, rect: ColumnRect,
        location_volumes: list[TerritoryVolume] | None = None, *,
        refine_role: ChunkRefineRole = "background", stages: GradePipelineStages | None = None,
        region_state_snapshot: Mapping[str, StateSnapshotEntry],
        working: SurfaceWorkingMaps,
    ) -> FineRefineResult:
        """Standalone single-rect operation; nested queued work does not publish."""
        result = await self._refine_rect(world, locations, writer, mat_ctx, surface_bundle,
            tile_gx, tile_gy, rect, location_volumes, refine_role=refine_role, stages=stages,
            region_state_snapshot=region_state_snapshot, working=working)
        writer.save_manifest()
        return result

    async def _refine_rect(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_bundle: SurfacePlanBundle,
        tile_gx: int,
        tile_gy: int,
        rect: ColumnRect,
        location_volumes: list[TerritoryVolume] | None = None,
        *,
        refine_role: ChunkRefineRole = "background",
        stages: GradePipelineStages | None = None,
        region_state_snapshot: Mapping[str, StateSnapshotEntry],
        working: SurfaceWorkingMaps,
    ) -> FineRefineResult:
        loc_volumes = location_volumes or [
            vol for _, vol in territory_volumes_by_location(world, locations)
        ]
        resolved = stages or GradePipelineStages.off()
        templates = await self._relief_templates(world) if resolved.mill else None
        result = await self._runner.refine_rects(
            world, locations, writer, mat_ctx, surface_bundle,
            tile_gx, tile_gy, [rect], loc_volumes,
            refine_role=refine_role,
            phase=refine_role,
            relief_templates_by_uid=templates,
            stages=resolved,
            region_state_snapshot=region_state_snapshot,
            working=working,
        )
        await persist_refine_grade_instances(self._relief_grade_repo, world, result)
        return result

    async def refine_queued_chunk(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_bundle: SurfacePlanBundle,
        tile_gx: int,
        tile_gy: int,
        cx: int,
        cy: int,
        *,
        stages: GradePipelineStages | None = None,
        region_state_snapshot: Mapping[str, StateSnapshotEntry],
        working: SurfaceWorkingMaps,
    ) -> FineRefineResult:
        rect = fine_chunk_rect(world, tile_gx, tile_gy, cx, cy)
        return await self._refine_rect(
            world, locations, writer, mat_ctx, surface_bundle,
            tile_gx, tile_gy, rect,
            refine_role="background",
            stages=stages,
            region_state_snapshot=region_state_snapshot,
            working=working,
        )

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

    # Compat for tests that called private _refine_rects
    async def _refine_rects(self, *args, **kwargs):
        return await self._runner.refine_rects(*args, **kwargs)
