"""Region entity store (not WP-20 per-cell patches).

StateChangeConsumer (step 10a) is the sole state writer, including tombstones.
Bake/generators and other callers must not invoke state write methods. Reads
are unrestricted; a read/bake owner may explicitly cleanup already tombstoned
orphans. This store never infers orphans from a partial region snapshot.
History is append-only by the writer contract; CRUD does not compute transitions.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.db.models.regionState import RegionStateRow


class IRegionStateRepository(ABC):
    @abstractmethod
    async def get(self, world_uid: str, region_uid: str) -> RegionStateRow | None: ...

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[RegionStateRow]:
        """Include tombstones so overlay readers can apply their fallback policy."""
        ...

    @abstractmethod
    async def upsert(self, state: RegionStateRow) -> None: ...

    @abstractmethod
    async def upsert_bulk(self, states: Sequence[RegionStateRow]) -> int: ...

    @abstractmethod
    async def mark_tombstone(
        self, world_uid: str, region_uid: str, *, updated_at: str,
    ) -> int:
        """Mark an existing row; a missing state is a no-op."""
        ...

    @abstractmethod
    async def mark_tombstones(
        self, world_uid: str, region_uids: Sequence[str], *, updated_at: str,
    ) -> int: ...

    @abstractmethod
    async def cleanup_orphans(self, world_uid: str) -> int:
        """Delete only already tombstoned states in this world, explicitly."""
        ...
