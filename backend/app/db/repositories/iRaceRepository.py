from abc import ABC, abstractmethod

from app.db.models.race import Race


class IRaceRepository(ABC):

    @abstractmethod
    async def get_by_id(self, race_uid: str) -> Race | None: ...

    @abstractmethod
    async def get_by_world(self, world_id: str) -> list[Race]: ...

    @abstractmethod
    async def create(self, race: Race) -> None: ...

    @abstractmethod
    async def update(self, race: Race) -> None: ...

    @abstractmethod
    async def upsert(self, race: Race) -> None: ...

    @abstractmethod
    async def delete(self, race_uid: str) -> None: ...
