from abc import ABC, abstractmethod

from app.db.models.connectionEdge import ConnectionEdge


class IConnectionEdgeRepository(ABC):

    @abstractmethod
    async def get_by_id(self, edge_uid: str) -> ConnectionEdge | None: ...

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[ConnectionEdge]: ...

    @abstractmethod
    async def upsert(self, edge: ConnectionEdge) -> None: ...

    @abstractmethod
    async def upsert_bulk(self, edges: list[ConnectionEdge]) -> int: ...

    @abstractmethod
    async def delete_by_world(self, world_uid: str) -> None: ...
