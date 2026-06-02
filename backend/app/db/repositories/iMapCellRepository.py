from abc import ABC, abstractmethod

from app.db.models.mapCell import MapCell


class IMapCellRepository(ABC):

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[MapCell]: ...

    @abstractmethod
    async def get_location_uids_with_cells(self, world_uid: str) -> set[str]: ...

    @abstractmethod
    async def upsert(self, cell: MapCell) -> None: ...

    @abstractmethod
    async def insert_bulk_ignore(self, cells: list[MapCell]) -> int:
        """Insert cells in a single transaction; silently skips positions that already exist.
        Returns the number of rows actually inserted."""
        ...

    @abstractmethod
    async def get_by_location(self, location_uid: str) -> list[MapCell]: ...

    @abstractmethod
    async def has_cells_for_location(self, location_uid: str) -> bool: ...

    @abstractmethod
    async def delete_by_world(self, world_uid: str) -> None: ...
