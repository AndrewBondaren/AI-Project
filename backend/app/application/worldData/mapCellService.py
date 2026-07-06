import logging
from dataclasses import asdict

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list
from app.db.models.mapCell import MapCell
from app.db.repositories.iMapCellRepository import IMapCellRepository

logger = logging.getLogger(__name__)

LayerKind = str  # "terrain" | "climate" | "ore" | "cave"


class MapCellService:
    """map_cells CRUD and layer upsert — no terrain generation orchestration (MR-7)."""

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
