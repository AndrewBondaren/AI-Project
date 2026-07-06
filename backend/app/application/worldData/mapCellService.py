import logging
from dataclasses import asdict

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list
from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.terrain.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.hydrology.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.passes.surfacePass import run_surface_pass
from app.application.worldData.generators.terrain.terrainGeneratorService import TerrainGeneratorService
from app.application.worldData.generators.terrain.worldMapSettings import n_base, terrain_chunk_columns
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.repositories.iMapCellRepository import IMapCellRepository

logger = logging.getLogger(__name__)

LayerKind = str  # "terrain" | "climate" | "ore" | "cave"


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
    ) -> ImportResult:
        pole_field = run_pole_resolve_pass(world, locations)
        heightmap = run_surface_pass(world, locations, pole_field)
        if heightmap is None:
            return ImportResult(total=0, succeeded=0, failed=0)

        hydrology_by_cell = {}
        if is_hydrology_enabled(world):
            hydro = hydrology_generator or HydrologyGeneratorService()
            hydro_result = hydro.apply(
                world,
                locations,
                heightmap,
                nodes=nodes or [],
                edges=edges or [],
            )
            hydrology_by_cell = hydro_result.cell_index.by_cell

        n_eff = run_gap_analysis(world, heightmap)

        total = 0
        succeeded = 0
        n_eff_gt = 0

        base = n_base(world)
        for v in n_eff.values():
            if v > base:
                n_eff_gt += 1

        chunk_size = terrain_chunk_columns(world)
        chunks = list(TerrainGeneratorService.iter_column_chunks(heightmap, chunk_size))
        for rect in chunks:
            chunk_cells = generator.generate_surface_chunk(
                world, locations, heightmap, n_eff, rect,
                hydrology_by_cell=hydrology_by_cell or None,
            )
            total += len(chunk_cells)
            result = await self.save_pass(chunk_cells, "terrain")
            succeeded += result.succeeded

        logger.info(
            "save_terrain_batch | world=%s cells=%d upserted=%d n_eff_gt_base=%d chunks=%d hydrology=%d",
            world_uid,
            total,
            succeeded,
            n_eff_gt,
            sum(1 for _ in chunks),
            len(hydrology_by_cell),
        )
        return ImportResult(total=total, succeeded=succeeded, failed=0)

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
