from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.db.models.locationEntryPoint import LocationEntryPoint


class ILocationEntryPointRepository(ABC):

    @abstractmethod
    async def get_by_location(self, location_uid: str) -> list[LocationEntryPoint]: ...

    @abstractmethod
    async def upsert_bulk(self, rows: Sequence[LocationEntryPoint]) -> int: ...
