from abc import ABC, abstractmethod

from app.db.models.namedLocation import NamedLocation


class INamedLocationRepository(ABC):

    @abstractmethod
    async def get_by_id(self, location_uid: str) -> NamedLocation | None: ...

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[NamedLocation]: ...

    @abstractmethod
    async def get_children(self, parent_uid: str) -> list[NamedLocation]: ...

    @abstractmethod
    async def get_tree(self, world_uid: str) -> dict[str, int]:
        """uid → depth для всех локаций мира через WITH RECURSIVE CTE."""
        ...

    @abstractmethod
    async def get_faction_access_bulk(
        self, location_uids: list[str]
    ) -> dict[str, list[tuple[str, bool]]]:
        """location_uid → [(faction_uid, is_allowed), ...] из location_faction_access."""
        ...

    @abstractmethod
    async def create(self, loc: NamedLocation) -> None: ...

    @abstractmethod
    async def update(self, loc: NamedLocation) -> None: ...

    @abstractmethod
    async def upsert(self, loc: NamedLocation) -> None: ...

    @abstractmethod
    async def delete(self, location_uid: str) -> None: ...
