from abc import ABC, abstractmethod

from app.db.models.connectionEdgeCell import ConnectionEdgeCell


class IConnectionEdgeCellRepository(ABC):

    @abstractmethod
    async def get_by_edge(self, edge_uid: str) -> list[ConnectionEdgeCell]: ...

    @abstractmethod
    async def replace_for_edge(self, edge_uid: str, cells: list[ConnectionEdgeCell]) -> int: ...

    @abstractmethod
    async def upsert_bulk(self, cells: list[ConnectionEdgeCell]) -> int: ...

    @abstractmethod
    async def delete_by_world(self, world_uid: str) -> None: ...
