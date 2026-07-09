from abc import ABC, abstractmethod

from app.db.models.connectionNode import ConnectionNode


class IConnectionNodeRepository(ABC):

    @abstractmethod
    async def get_by_id(self, node_uid: str) -> ConnectionNode | None: ...

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[ConnectionNode]: ...

    @abstractmethod
    async def upsert(self, node: ConnectionNode) -> None: ...

    @abstractmethod
    async def upsert_bulk(self, nodes: list[ConnectionNode]) -> int: ...

    @abstractmethod
    async def delete_by_world(self, world_uid: str) -> None: ...
