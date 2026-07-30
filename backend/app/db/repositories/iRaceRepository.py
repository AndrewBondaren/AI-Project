from abc import ABC, abstractmethod

from app.db.models.race import Race


class IRaceRepository(ABC):

    @abstractmethod
    async def get_by_id(self, template_uid: str) -> Race | None: ...

    @abstractmethod
    async def list_all(self) -> list[Race]: ...

    @abstractmethod
    async def get_by_uids(self, uids: list[str]) -> list[Race]: ...

    @abstractmethod
    async def create(self, race: Race) -> None: ...

    @abstractmethod
    async def update(self, race: Race) -> None: ...

    @abstractmethod
    async def upsert(self, race: Race) -> None: ...

    @abstractmethod
    async def delete(self, template_uid: str) -> None: ...
