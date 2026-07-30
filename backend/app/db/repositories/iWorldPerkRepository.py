from abc import ABC, abstractmethod

from app.db.models.world_perk import WorldPerk


class IWorldPerkRepository(ABC):

    @abstractmethod
    async def get_by_id(self, template_uid: str) -> WorldPerk | None: ...

    @abstractmethod
    async def list_all(self) -> list[WorldPerk]: ...

    @abstractmethod
    async def get_by_uids(self, uids: list[str]) -> list[WorldPerk]: ...

    @abstractmethod
    async def create(self, perk: WorldPerk) -> None: ...

    @abstractmethod
    async def update(self, perk: WorldPerk) -> None: ...

    @abstractmethod
    async def upsert(self, perk: WorldPerk) -> None: ...

    @abstractmethod
    async def delete(self, template_uid: str) -> None: ...
