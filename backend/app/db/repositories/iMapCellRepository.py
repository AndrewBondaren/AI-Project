from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

from app.db.models.mapCell import MapCell


class IMapCellRepository(ABC):

    @asynccontextmanager
    async def persist_session(self) -> AsyncIterator[None]:
        """Batch writes without per-call commit; one COMMIT on exit (TR-PERF-2)."""
        yield

    @asynccontextmanager
    async def persist_session_on(self, conn: aiosqlite.Connection) -> AsyncIterator[None]:
        """Batch writes on explicit connection (TR-PAR-6 bootstrap writer)."""
        yield

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[MapCell]: ...

    @abstractmethod
    async def has_world_cells(self, world_uid: str) -> bool:
        """True if any map_cells row exists for world_uid."""

    @abstractmethod
    async def get_location_uids_with_cells(self, world_uid: str) -> set[str]: ...

    @abstractmethod
    async def upsert(self, cell: MapCell) -> None: ...

    @abstractmethod
    async def upsert_settlement_surface(self, cells: list[MapCell]) -> int:
        """Merge settlement footprint onto existing surface cells (location_uid + urban terrain)."""
        ...

    @abstractmethod
    async def insert_bulk_ignore(
        self,
        cells: list[MapCell],
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> int:
        """Insert cells in a single transaction; silently skips positions that already exist.
        Returns the number of rows actually inserted."""
        ...

    @abstractmethod
    async def insert_terrain_bulk(
        self,
        cells: list[MapCell],
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> int:
        """Plain INSERT for empty-world bootstrap (TR-PERF-3); caller guarantees no PK clash."""

    @abstractmethod
    async def upsert_terrain_skeleton(
        self,
        cells: list[MapCell],
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> int:
        """Upsert system_terrain for skeleton cells; skips building_element cells."""
        ...

    @abstractmethod
    async def upsert_climate_fields(
        self,
        cells: list[MapCell],
        *,
        conn: aiosqlite.Connection | None = None,
    ) -> int:
        """Upsert temperature_base, rainfall, location_uid, system_terrain (liquid overlay)."""
        ...

    @abstractmethod
    async def upsert_ore_markers(self, cells: list[MapCell]) -> int:
        """Upsert system_material ore markers."""
        ...

    @abstractmethod
    async def upsert_cave_carve(self, cells: list[MapCell]) -> int:
        """Carve caves — system_terrain only when no ore material."""
        ...

    @abstractmethod
    async def get_z_slice(
        self,
        world_uid: str,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        z_min: int,
        z_max: int,
    ) -> list[MapCell]: ...

    @abstractmethod
    async def get_by_location(self, location_uid: str) -> list[MapCell]: ...

    @abstractmethod
    async def has_column_cells(self, world_uid: str, x: int, y: int) -> bool:
        """True if any z-level exists at fine grid column (x, y)."""

    @abstractmethod
    async def has_cells_for_location(self, location_uid: str) -> bool: ...

    @abstractmethod
    async def delete_by_world(self, world_uid: str) -> None: ...
