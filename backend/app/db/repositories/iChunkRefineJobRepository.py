from abc import ABC, abstractmethod

from app.db.models.chunkRefineJob import ChunkRefineJob


class IChunkRefineJobRepository(ABC):

    @abstractmethod
    async def upsert(self, job: ChunkRefineJob) -> None: ...

    @abstractmethod
    async def pop_next_pending(self, world_uid: str) -> ChunkRefineJob | None: ...

    @abstractmethod
    async def mark_complete(self, job_uid: str, *, content_hash: str | None = None) -> None: ...

    @abstractmethod
    async def has_pending(self, world_uid: str, gx: int, gy: int, cx: int, cy: int) -> bool: ...
