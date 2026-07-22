"""detailed_bake — offline L2 for location territory and/or wilderness tiles.

Single shared refine loop; scope policies select tiles/rects/volumes/role.
See docs/tz_world_pack_storage.md § Bake modes; .cursor/plans/detailed-bake-smell-fixes.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.climate.climatePackBakeOrchestrator import (
    ClimatePackBakeOrchestrator,
)
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volume_for_location,
    territory_volumes_by_location,
)
from app.application.worldData.pack.read.parentLightLoad import require_parent_light
from app.application.worldData.pack.refine.fineChunkRunner import FineChunkRunner
from app.application.worldData.pack.refine.meterChunkGeom import (
    expected_meter_chunks,
    rects_for_macro_tile,
    rects_overlapping_volume,
    tiles_covering_volume,
)
from app.application.worldData.persistResult import PersistResult
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.worldPack.detailedBakeScope import (
    DetailedBakeRequest,
    DetailedBakeScopeKind,
    refine_role_for_detailed_scope,
)
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

RectsForTile = Callable[[int, int], list[ColumnRect]]


@dataclass(frozen=True)
class PackDetailedBakeResult:
    scope: DetailedBakeScopeKind
    terrain: PersistResult
    tiles_refined: int = 0
    wilderness_chunks: int = 0
    climate_fine_tiles: int = 0
    location_uid: str | None = None


@dataclass
class _FineAggregate:
    persist: PersistResult = field(default_factory=lambda: PersistResult.from_counts(0, 0))
    chunks_written: int = 0
    tiles_refined: int = 0
    meter_surface_z: dict[tuple[int, int], int] = field(default_factory=dict)


class PackDetailedBakeOrchestrator:
    """Offline L2 detailed bake — location and wilderness scopes share one refine loop."""

    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        runner: FineChunkRunner | None = None,
        climate_bake: ClimatePackBakeOrchestrator | None = None,
        bake_defaults: PackBakeDefaults | None = None,
    ) -> None:
        self._defaults = bake_defaults or PackBakeDefaults.canonical_defaults()
        self._runner = runner or FineChunkRunner(terrain)
        self._climate = climate_bake or ClimatePackBakeOrchestrator(
            bake_defaults=self._defaults,
        )

    async def bake(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        request: DetailedBakeRequest,
    ) -> PackDetailedBakeResult:
        if request.scope == "location":
            return await self._bake_location_scope(
                world, locations, writer, mat_ctx, surface_ctx, request,
            )
        return await self._bake_wilderness_scope(
            world, locations, writer, mat_ctx, surface_ctx, request,
        )

    async def _bake_location_scope(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        request: DetailedBakeRequest,
    ) -> PackDetailedBakeResult:
        location_uid = request.location_uid
        assert location_uid is not None
        location = next((loc for loc in locations if loc.location_uid == location_uid), None)
        if location is None:
            raise ValueError(f"location_uid not found: {location_uid}")
        volume = territory_volume_for_location(world, location)
        if volume is None:
            raise ValueError(
                f"location {location_uid} has no territory volume (missing map_x/map_y)",
            )

        tiles = tiles_covering_volume(world, volume)
        if not tiles:
            raise ValueError(f"location {location_uid}: no macro-tiles for territory")

        aggregate = await self._refine_tiles(
            world, locations, writer, mat_ctx, surface_ctx,
            tiles,
            rects_for_tile=lambda gx, gy: rects_overlapping_volume(world, volume, gx, gy),
            location_volumes=[volume],
            refine_role=refine_role_for_detailed_scope("location"),
            expected_chunks_for_status=None,
        )

        climate_fine_tiles = 0
        if self._defaults.detailed_include_climate_fine:
            for gx, gy in tiles:
                if self._climate.bake_fine_tile_with_parent(
                    world, surface_ctx, writer, gx, gy,
                    l2_surface_z=aggregate.meter_surface_z or None,
                    locations=locations,
                    require_parent=True,
                ):
                    climate_fine_tiles += 1

        writer.recalc_manifest_counters()
        writer.save_manifest()
        return PackDetailedBakeResult(
            scope="location",
            terrain=aggregate.persist,
            tiles_refined=aggregate.tiles_refined,
            wilderness_chunks=aggregate.chunks_written,
            climate_fine_tiles=climate_fine_tiles,
            location_uid=location_uid,
        )

    async def _bake_wilderness_scope(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        request: DetailedBakeRequest,
    ) -> PackDetailedBakeResult:
        tiles = self._wilderness_tiles(
            writer,
            max_tiles=request.max_tiles,
            tile_gx=request.tile_gx,
            tile_gy=request.tile_gy,
        )
        volumes = [vol for _, vol in territory_volumes_by_location(world, locations)]

        aggregate = await self._refine_tiles(
            world, locations, writer, mat_ctx, surface_ctx,
            tiles,
            rects_for_tile=lambda gx, gy: rects_for_macro_tile(world, gx, gy),
            location_volumes=volumes,
            refine_role=refine_role_for_detailed_scope("wilderness"),
            expected_chunks_for_status=lambda gx, gy: expected_meter_chunks(world, gx, gy),
        )

        writer.recalc_manifest_counters()
        writer.save_manifest()
        return PackDetailedBakeResult(
            scope="wilderness",
            terrain=aggregate.persist,
            tiles_refined=aggregate.tiles_refined,
            wilderness_chunks=aggregate.chunks_written,
            climate_fine_tiles=0,
            location_uid=None,
        )

    def _wilderness_tiles(
        self,
        writer: WorldPackWriter,
        *,
        max_tiles: int,
        tile_gx: int | None = None,
        tile_gy: int | None = None,
    ) -> list[tuple[int, int]]:
        if tile_gx is not None and tile_gy is not None:
            tile = writer.manifest.tile_entry(tile_gx, tile_gy)
            if tile is None or not tile.world_map_path:
                raise ValueError(
                    f"wilderness tile=({tile_gx},{tile_gy}) has no L0 world_map_path "
                    "(run full/light bake first)",
                )
            if tile.wilderness_refine_status == "complete":
                return []
            return [(tile_gx, tile_gy)]

        out: list[tuple[int, int]] = []
        for tile in writer.manifest.tiles:
            if not tile.world_map_path:
                continue
            if tile.wilderness_refine_status == "complete":
                continue
            out.append((tile.gx, tile.gy))
        out.sort(key=lambda t: (t[1], t[0]))
        if max_tiles > 0:
            return out[:max_tiles]
        return out

    async def _refine_tiles(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        tiles: list[tuple[int, int]],
        *,
        rects_for_tile: RectsForTile,
        location_volumes: list[TerritoryVolume],
        refine_role: ChunkRefineRole,
        expected_chunks_for_status: Callable[[int, int], int] | None,
        phase: str = "detailed",
    ) -> _FineAggregate:
        tile_m = cell_size_m(world)
        reader = WorldPackReader(writer.paths)
        cache = writer.parent_light_cache
        for gx, gy in tiles:
            require_parent_light(
                world.world_uid, gx, gy,
                reader=reader, cache=cache, tile_m=tile_m,
            )

        aggregate = _FineAggregate()
        for gx, gy in tiles:
            rects = rects_for_tile(gx, gy)
            if not rects:
                continue
            refined = await self._runner.refine_rects(
                world, locations, writer, mat_ctx, surface_ctx,
                gx, gy, rects, location_volumes,
                refine_role=refine_role,
                phase=phase,
            )
            for key, z in refined.meter_surface_z.items():
                prev = aggregate.meter_surface_z.get(key)
                if prev is None or z > prev:
                    aggregate.meter_surface_z[key] = z
            aggregate.persist = PersistResult.from_counts(
                aggregate.persist.total + refined.persist.total,
                aggregate.persist.succeeded + refined.persist.succeeded,
                failed=aggregate.persist.failed + refined.persist.failed,
            )
            aggregate.chunks_written += refined.wilderness_chunks_written
            aggregate.tiles_refined += 1
            if expected_chunks_for_status is not None:
                writer.recalc_wilderness_status(
                    gx, gy,
                    expected_chunks=expected_chunks_for_status(gx, gy),
                )
        return aggregate
