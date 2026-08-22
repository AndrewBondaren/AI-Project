"""Pack writes after ColumnRect compute — wilderness, location flush, grade acc."""

from __future__ import annotations

import asyncio

from app.application.worldData.gradeInstanceMerge import merge_grade_instances
from app.application.worldData.gradeVertexSystem import emit_relief_grade_systems
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_location_terrain_persist,
    log_pack_wilderness_chunk_done,
    log_pack_wilderness_chunk_persist,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.mapCellToFineTerrainWire import (
    cells_to_fine_terrain_chunk,
)
from app.application.worldData.pack.refine.entryRingGeom import (
    tile_local_chunk_indices,
    wilderness_chunk_origin,
)
from app.application.worldData.pack.refine.fineRefineResult import FineRefineResult
from app.application.worldData.pack.refine.fineTileContext import (
    ChunkComputeResult,
    FineTileContext,
    VertexSlotSeam,
)
from app.application.worldData.persistResult import PersistResult
from app.application.worldData.generators.terrain.relief.validate.gradeCellRays import (
    validate_grade_cell_empty_rays,
)
from app.dataModel.terrain.relief.gradeRimRay import (
    GradeRimRay,
    merge_grade_rim_rays,
    pack_rim_slot_rays,
)
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem
from app.dataModel.worldPack.territoryVolume import TerritoryVolume, inside_location_volume
from app.db.models.mapCell import MapCell


def partition_chunk_cells(
    cells: list[MapCell],
    location_pairs: list[tuple[str, TerritoryVolume]],
    volumes: list[TerritoryVolume],
) -> tuple[list[MapCell], dict[str, list[MapCell]], set[str]]:
    wilderness: list[MapCell] = []
    location_additions: dict[str, list[MapCell]] = {}
    loc_hits: set[str] = set()
    for cell in cells:
        hit = location_for_cell(cell.x, cell.y, cell.z, location_pairs)
        if hit is not None:
            location_uid, _ = hit
            loc_hits.add(location_uid)
            location_additions.setdefault(location_uid, []).append(cell)
        elif not inside_location_volume(cell.x, cell.y, cell.z, volumes):
            wilderness.append(cell)
    return wilderness, location_additions, loc_hits


def location_for_cell(
    x: int,
    y: int,
    z: int,
    location_volumes: list[tuple[str, TerritoryVolume]],
) -> tuple[str, TerritoryVolume] | None:
    for location_uid, volume in location_volumes:
        if volume.contains(x, y, z):
            return location_uid, volume
    return None


class FineChunkPersist:
    """Single-writer pack side of refine_rects. Generate stays in compute_rect."""

    def __init__(self, ctx: FineTileContext, writer: WorldPackWriter) -> None:
        self._ctx = ctx
        self._writer = writer
        self._location_cells: dict[str, list[MapCell]] = {}
        self._meter_surface_z: dict[tuple[int, int], int] = {}
        self._grade_acc: list[ReliefGradeInstance] = []
        self._ray_acc: list[GradeRimRay] = []
        self._seam_acc: list[tuple[ColumnRect, tuple[VertexSlotSeam, ...]]] = []
        self._total_cells = 0
        self._written = 0
        self._materialize_s = 0.0
        self._grade_s = 0.0
        self._lock = asyncio.Lock()

    def persist_rect(self, result: ChunkComputeResult) -> None:
        """Caller serializes (serial loop or ``persist_rect_locked``)."""
        ctx = self._ctx
        self._materialize_s += result.materialize_s
        self._grade_s += result.grade_s
        self._note_surface_z(result.cells)
        wilderness, loc_additions, loc_hits = partition_chunk_cells(
            result.cells, ctx.location_pairs, ctx.volumes,
        )
        for location_uid, additions in loc_additions.items():
            self._location_cells.setdefault(location_uid, []).extend(additions)
        cx, cy = tile_local_chunk_indices(result.rect, ctx.meter_bbox, ctx.chunk_size)
        log_pack_wilderness_chunk_persist(
            ctx.world_uid,
            phase=ctx.phase_name,
            tile_gx=ctx.tile_gx,
            tile_gy=ctx.tile_gy,
            chunk_idx=result.chunk_idx,
            chunks_total=ctx.chunks_total,
            refine_role=ctx.refine_role,
            wilderness_cells=len(wilderness),
            location_uids=sorted(loc_hits),
            pool_workers=ctx.workers,
        )
        if wilderness:
            origin_x, origin_y = wilderness_chunk_origin(
                ctx.meter_bbox, cx, cy, ctx.chunk_size,
            )
            chunk = cells_to_fine_terrain_chunk(
                cx, cy, ctx.chunk_size, origin_x, origin_y, wilderness,
            )
            self._writer.write_wilderness_chunk(
                ctx.tile_gx, ctx.tile_gy, chunk,
                refine_role=ctx.refine_role,  # type: ignore[arg-type]
            )
            self._total_cells += len(wilderness)
            self._written += 1
            self._writer.maybe_checkpoint_manifest(self._written)
        log_pack_wilderness_chunk_done(
            ctx.world_uid,
            phase=ctx.phase_name,
            tile_gx=ctx.tile_gx,
            tile_gy=ctx.tile_gy,
            chunk_idx=result.chunk_idx,
            chunks_total=ctx.chunks_total,
            rect=result.rect,
            refine_role=ctx.refine_role,
            generated_cells=len(result.cells),
            wilderness_cells=len(wilderness),
            location_uids=sorted(loc_hits),
            started_at=result.chunk_t0,
            pool_workers=ctx.workers,
        )
        self._grade_acc.extend(result.chunk_grades)
        self._ray_acc.extend(result.rim_rays)
        self._seam_acc.append((result.rect, result.vertex_seams))

    async def persist_rect_locked(self, result: ChunkComputeResult) -> None:
        async with self._lock:
            self.persist_rect(result)

    def finish(self) -> FineRefineResult:
        ctx = self._ctx
        for location_uid, loc_cells in self._location_cells.items():
            volume = next(
                (vol for uid, vol in ctx.location_pairs if uid == location_uid),
                None,
            )
            if volume is None or not loc_cells:
                continue
            log_pack_location_terrain_persist(
                ctx.world_uid,
                location_uid=location_uid,
                cells=len(loc_cells),
                pool_workers=ctx.workers,
            )
            chunk = cells_to_fine_terrain_chunk(
                0, 0, ctx.chunk_size, volume.x0, volume.y0, loc_cells,
            )
            self._writer.write_location_terrain(
                location_uid, chunk, territory_volume=volume,
            )
            self._total_cells += len(loc_cells)
        cells = set(self._meter_surface_z)
        slots = pack_rim_slot_rays(
            merge_grade_rim_rays(self._ray_acc),
            cells=cells,
        )
        self._write_grade_ray_sidecars(slots)
        validate_grade_cell_empty_rays(cells, slots)
        self._writer.recalc_manifest_counters()
        self._writer.save_manifest()
        grade_instances = (
            merge_grade_instances(self._grade_acc) if self._grade_acc else ()
        )
        grade_systems: tuple[ReliefGradeSystem, ...] = ()
        if grade_instances:
            # T-3c after C29 catalog merge. Does not change z/fill.
            grade_instances, grade_systems = emit_relief_grade_systems(
                grade_instances,
                traces=self._seam_acc,
                catalog=ctx.catalog,
            )
        return FineRefineResult(
            persist=PersistResult.from_counts(self._total_cells, self._total_cells),
            wilderness_chunks_written=self._written,
            rect_count=ctx.chunks_total,
            meter_surface_z=self._meter_surface_z,
            grade_instances=grade_instances,
            grade_systems=grade_systems,
            rim_rays=slots,
            materialize_s=self._materialize_s,
            grade_s=self._grade_s,
        )

    def _note_surface_z(self, cells: list[MapCell]) -> None:
        for cell in cells:
            key = (int(cell.x), int(cell.y))
            prev = self._meter_surface_z.get(key)
            if prev is None or cell.z > prev:
                self._meter_surface_z[key] = int(cell.z)

    def _write_grade_ray_sidecars(self, slots: tuple[GradeRimRay, ...]) -> None:
        if not slots:
            return
        ctx = self._ctx
        wilderness: list[GradeRimRay] = []
        by_loc: dict[str, list[GradeRimRay]] = {}
        for ray in slots:
            z = self._meter_surface_z.get((ray.x, ray.y))
            hit = (
                location_for_cell(ray.x, ray.y, z, ctx.location_pairs)
                if z is not None
                else None
            )
            if hit is not None:
                by_loc.setdefault(hit[0], []).append(ray)
            else:
                wilderness.append(ray)
        if wilderness:
            self._writer.merge_grade_rays_tile(ctx.tile_gx, ctx.tile_gy, wilderness)
        for location_uid, rays in by_loc.items():
            self._writer.merge_grade_rays_location(location_uid, rays)
