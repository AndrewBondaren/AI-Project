from abc import ABC, abstractmethod

from app.db.models.world_perk import WorldPerk


class IWorldPerkRepository(ABC):

    @abstractmethod
    async def get_by_id(self, perk_uid: str) -> WorldPerk | None: ...

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[WorldPerk]: ...

    @abstractmethod
    async def create(self, perk: WorldPerk) -> None: ...

    @abstractmethod
    async def update(self, perk: WorldPerk) -> None: ...

    @abstractmethod
    async def upsert(self, perk: WorldPerk) -> None: ...

    @abstractmethod
    async def delete(self, perk_uid: str) -> None: ...
