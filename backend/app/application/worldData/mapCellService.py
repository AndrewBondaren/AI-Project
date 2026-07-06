import logging
from dataclasses import asdict
from typing import Literal

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list
from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.terrain.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.terrainGeneratorService import TerrainGeneratorService
from app.application.worldData.generators.terrain.worldMapSettings import terrain_chunk_columns
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.repositories.iMapCellRepository import IMapCellRepository

logger = logging.getLogger(__name__)

LayerKind = str  # "terrain" | "climate" | "ore" | "cave"
SurfaceMode = Literal["bootstrap", "full"]


class MapCellService:

    def __init__(self, repo: IMapCellRepository) -> None:
        self._repo = repo

    async def get_all(self, world_uid: str) -> list[MapCell]:
        return await self._repo.get_by_world(world_uid)

    async def export(self, world_uid: str) -> list[dict]:
        cells = await self._repo.get_by_world(world_uid)
        return [asdict(c) for c in cells]

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        def prepare(row: dict) -> MapCell:
            return MapCell(**{**row, "world_uid": world_uid})
        return await import_list(data, prepare, self._repo.upsert)

    async def clear(self, world_uid: str) -> None:
        await self._repo.delete_by_world(world_uid)

    async def get_location_uids_with_cells(self, world_uid: str) -> frozenset[str]:
        uids = await self._repo.get_location_uids_with_cells(world_uid)
        return frozenset(uids)

    async def save_generated(self, cells: list[MapCell]) -> ImportResult:
        """Legacy: INSERT OR IGNORE — used by lazy nodes."""
        inserted = await self._repo.insert_bulk_ignore(cells)
        return ImportResult(total=len(cells), succeeded=inserted, failed=0)

    async def save_settlement_surface(self, cells: list[MapCell]) -> ImportResult:
        """Outdoor settlement footprint — merge onto world surface grid."""
        merged = await self._repo.upsert_settlement_surface(cells)
        return ImportResult(total=len(cells), succeeded=merged, failed=0)

    async def save_pass(self, cells: list[MapCell], layer: LayerKind) -> ImportResult:
        if layer == "terrain":
            n = await self._repo.upsert_terrain_skeleton(cells)
        elif layer == "climate":
            n = await self._repo.upsert_climate_fields(cells)
        elif layer == "ore":
            n = await self._repo.upsert_ore_markers(cells)
        elif layer == "cave":
            n = await self._repo.upsert_cave_carve(cells)
        else:
            raise ValueError(f"unknown layer kind: {layer}")
        return ImportResult(total=len(cells), succeeded=n, failed=0)

    def plan_bootstrap_tiles(
        self,
        world,
        locations: list,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        max_tiles: int | None = 16,
    ) -> list[tuple[int, int]]:
        from app.application.worldData.generators.coordinates import cell_size_m
        from app.application.worldData.generators.terrain.passes.bootstrapMacroTiles import (
            bootstrap_macro_tiles,
        )
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
            prepare_surface_terrain_context,
        )

        ctx = prepare_surface_terrain_context(
            world,
            locations,
            nodes=nodes,
            edges=edges,
            hydrology_generator=hydrology_generator,
        )
        if ctx is None:
            return []
        return bootstrap_macro_tiles(
            world,
            locations,
            ctx.coarse_hydro,
            ctx.sparse_meter_hydro,
            max_tiles=max_tiles,
        )

    async def _materialize_fine_tile(
        self,
        generator: TerrainGeneratorService,
        world,
        locations: list,
        ctx,
        tile_gx: int,
        tile_gy: int,
    ) -> ImportResult:
        from app.application.worldData.generators.coordinates import cell_size_m
        from app.application.worldData.generators.coordinates.worldTile import (
            iter_meter_chunks,
            meter_bbox_for_tile,
        )
        from app.application.worldData.generators.terrain.hydrology.meterHydrologyIndex import (
            merge_meter_hydro_for_tile,
        )
        from app.application.worldData.generators.terrain.passes.surfacePass import build_fine_surface_tile
        from app.application.worldData.generators.terrain.types import SurfaceHeightmap

        cell_m = cell_size_m(world)
        fine_z = build_fine_surface_tile(
            world, ctx.pole_field, tile_gx, tile_gy, ctx.coarse_surface_z,
        )
        for (xm, ym), z in ctx.meter_z_overrides.items():
            if xm // cell_m == tile_gx and ym // cell_m == tile_gy:
                fine_z[(xm, ym)] = z

        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        heightmap = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=meter_bbox,
            surface_z=fine_z,
        )
        tile_hydro = merge_meter_hydro_for_tile(
            tile_gx, tile_gy, cell_m, ctx.coarse_hydro, ctx.sparse_meter_hydro,
        )
        n_eff = run_gap_analysis(world, heightmap)
        chunk_size = terrain_chunk_columns(world)

        total = 0
        succeeded = 0
        for rect in iter_meter_chunks(meter_bbox, chunk_size):
            chunk_cells = generator.generate_surface_chunk(
                world,
                locations,
                heightmap,
                n_eff,
                rect,
                hydrology_by_cell=tile_hydro or None,
            )
            total += len(chunk_cells)
            result = await self.save_pass(chunk_cells, "terrain")
            succeeded += result.succeeded
        return ImportResult(total=total, succeeded=succeeded, failed=0)

    async def save_terrain_batch(
        self,
        world_uid: str,
        generator: TerrainGeneratorService,
        world,
        locations: list,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        surface_mode: SurfaceMode = "bootstrap",
        max_tiles: int | None = 16,
    ) -> ImportResult:
        from app.application.worldData.generators.coordinates import cell_size_m, iter_macro_tiles
        from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations
        from app.application.worldData.generators.terrain.passes.bootstrapMacroTiles import (
            bootstrap_macro_tiles,
        )
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
            prepare_surface_terrain_context,
        )

        macro_bbox = grid_bbox_from_locations(world, locations)
        if macro_bbox is None:
            return ImportResult(total=0, succeeded=0, failed=0)

        ctx = prepare_surface_terrain_context(
            world,
            locations,
            nodes=nodes,
            edges=edges,
            hydrology_generator=hydrology_generator,
        )
        if ctx is None:
            return ImportResult(total=0, succeeded=0, failed=0)

        cell_m = cell_size_m(world)
        if surface_mode == "full":
            tiles = list(iter_macro_tiles(macro_bbox))
        else:
            tiles = bootstrap_macro_tiles(
                world,
                locations,
                ctx.coarse_hydro,
                ctx.sparse_meter_hydro,
                max_tiles=max_tiles,
            )

        total = 0
        succeeded = 0
        for tile_gx, tile_gy in tiles:
            tile_result = await self._materialize_fine_tile(
                generator, world, locations, ctx, tile_gx, tile_gy,
            )
            total += tile_result.total
            succeeded += tile_result.succeeded

        logger.info(
            "save_terrain_batch | world=%s mode=%s fine tiles=%d cells=%d upserted=%d cell_m=%d",
            world_uid,
            surface_mode,
            len(tiles),
            total,
            succeeded,
            cell_m,
        )
        return ImportResult(total=total, succeeded=succeeded, failed=0)

    async def materialize_macro_tile(
        self,
        world_uid: str,
        generator: TerrainGeneratorService,
        world,
        locations: list,
        tile_gx: int,
        tile_gy: int,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
    ) -> ImportResult:
        """Fine grid for one macro tile (map_cell_size_m² × subsurface columns)."""
        from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
            prepare_surface_terrain_context,
        )

        if grid_bbox_from_locations(world, locations) is None:
            return ImportResult(total=0, succeeded=0, failed=0)

        ctx = prepare_surface_terrain_context(
            world,
            locations,
            nodes=nodes,
            edges=edges,
            hydrology_generator=hydrology_generator,
        )
        if ctx is None:
            return ImportResult(total=0, succeeded=0, failed=0)

        result = await self._materialize_fine_tile(
            generator, world, locations, ctx, tile_gx, tile_gy,
        )
        logger.info(
            "materialize_macro_tile | world=%s tile=(%d,%d) cells=%d upserted=%d",
            world_uid, tile_gx, tile_gy, result.total, result.succeeded,
        )
        return result

    async def save_z_slice(
        self,
        generator: TerrainGeneratorService,
        world,
        locations: list,
        gx: int,
        gy: int,
        z_lo: int,
        z_hi: int,
    ) -> ImportResult:
        pole_field = run_pole_resolve_pass(world, locations)
        cells      = generator.generate_z_slice(
            world, locations, pole_field, gx, gy, z_lo, z_hi,
        )
        return await self.save_pass(cells, "terrain")

    async def get_z_slice(
        self,
        world_uid: str,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        z_min: int,
        z_max: int,
    ) -> list[MapCell]:
        return await self._repo.get_z_slice(
            world_uid, x_min, x_max, y_min, y_max, z_min, z_max,
        )
