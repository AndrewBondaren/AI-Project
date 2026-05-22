from abc import ABC, abstractmethod

from app.db.models.named_location import NamedLocation


class INamedLocationRepository(ABC):

    @abstractmethod
    async def get_by_id(self, location_uid: str) -> NamedLocation | None: ...

    @abstractmethod
    async def get_by_world(self, world_id: str) -> list[NamedLocation]: ...

    @abstractmethod
    async def get_children(self, parent_uid: str) -> list[NamedLocation]: ...

    @abstractmethod
    async def create(self, loc: NamedLocation) -> None: ...

    @abstractmethod
    async def update(self, loc: NamedLocation) -> None: ...

    @abstractmethod
    async def upsert(self, loc: NamedLocation) -> None: ...

    @abstractmethod
    async def delete(self, location_uid: str) -> None: ...
