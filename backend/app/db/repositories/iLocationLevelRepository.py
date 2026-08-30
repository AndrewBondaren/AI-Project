from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.db.models.locationLevel import LocationLevel


class ILocationLevelRepository(ABC):

    @abstractmethod
    async def get_by_location(self, location_uid: str) -> list[LocationLevel]: ...

    @abstractmethod
    async def upsert_bulk(self, rows: Sequence[LocationLevel]) -> int: ...
