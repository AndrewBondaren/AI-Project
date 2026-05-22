from abc import ABC, abstractmethod

from app.db.models.world import World


class IWorldRepository(ABC):

    @abstractmethod
    async def get_by_id(self, world_id: str) -> World | None: ...

    @abstractmethod
    async def get_all(self) -> list[World]: ...

    @abstractmethod
    async def create(self, world: World) -> None: ...

    @abstractmethod
    async def update(self, world: World) -> None: ...

    @abstractmethod
    async def increment_tick(self, world_id: str) -> int: ...
