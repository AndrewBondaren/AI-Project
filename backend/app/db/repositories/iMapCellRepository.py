from abc import ABC, abstractmethod

from app.db.models.mapCell import MapCell


class IMapCellRepository(ABC):

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[MapCell]: ...

    @abstractmethod
    async def upsert(self, cell: MapCell) -> None: ...

    @abstractmethod
    async def delete_by_world(self, world_uid: str) -> None: ...
