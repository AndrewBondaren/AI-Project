import logging
from contextlib import asynccontextmanager
from dataclasses import asdict

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list
from app.application.worldData.generators.terrain.worldMapSettings import n_base, world_z_min
from app.application.worldData.sceneLoad import SCENE_LOAD_XY_RADIUS
from app.db.models.mapCell import MapCell
from app.db.models.world import World
from app.db.repositories.iMapCellRepository import IMapCellRepository

logger = logging.getLogger(__name__)

LayerKind = str  # "terrain" | "climate" | "ore" | "cave"


class MapCellService:
    """map_cells CRUD and layer upsert — no terrain generation orchestration (MR-7)."""

    def __init__(self, repo: IMapCellRepository) -> None:
        self._repo = repo

    @asynccontextmanager
    async def bulk_persist_session(self):
        """TR-PERF-2: defer commit across multiple save_pass calls."""
        async with self._repo.persist_session():
            yield

    @asynccontextmanager
    async def bulk_write_session(self, *, enabled: bool = True):
        """TR-PERF-4: PRAGMA tuning for bootstrap bulk persist."""
        if not enabled:
            yield
            return
        async with self._repo.bulk_write_session():
            yield

    async def has_world_cells(self, world_uid: str) -> bool:
        return await self._repo.has_world_cells(world_uid)

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

    async def has_column_cells(self, world_uid: str, x: int, y: int) -> bool:
        return await self._repo.has_column_cells(world_uid, x, y)

    async def get_scene_volume(
        self,
        world: World,
        x: int,
        y: int,
        z: int,
        *,
        xy_radius: int = SCENE_LOAD_XY_RADIUS,
        z_below: int | None = None,
        z_above: int = 0,
    ) -> list[MapCell]:
        """TR-LAZY-LOAD: 3D bbox around scene anchor for gameplay/debug."""
        depth = z_below if z_below is not None else n_base(world)
        z_lo = max(world_z_min(world), z - depth)
        z_hi = z + z_above
        r = max(0, xy_radius)
        return await self.get_z_slice(
            world.world_uid,
            x - r, x + r,
            y - r, y + r,
            z_lo, z_hi,
        )

    async def save_generated(self, cells: list[MapCell]) -> ImportResult:
        """Legacy: INSERT OR IGNORE — scope ``minimal_repair`` (lazy nodes).

        Insert matrix: ``docs/tz_terrain_generation.md`` § TR-PERF-DEBT-4.
        """
        inserted = await self._repo.insert_bulk_ignore(cells)
        return ImportResult(total=len(cells), succeeded=inserted, failed=0)

    async def save_settlement_surface(self, cells: list[MapCell]) -> ImportResult:
        """Outdoor settlement footprint — merge onto world surface grid."""
        merged = await self._repo.upsert_settlement_surface(cells)
        return ImportResult(total=len(cells), succeeded=merged, failed=0)

    async def save_pass(
        self,
        cells: list[MapCell],
        layer: LayerKind,
        *,
        insert_only: bool = False,
    ) -> ImportResult:
        """Layer upsert; terrain ``insert_only`` → plain INSERT (TR-PERF-3).

        Backlog: replace flag with ``TerrainPersistScope`` — § TR-PERF-DEBT-3.
        Insert matrix: § TR-PERF-DEBT-4.
        """
        if layer == "terrain":
            if insert_only:
                n = await self._repo.insert_terrain_bulk(cells)
            else:
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
