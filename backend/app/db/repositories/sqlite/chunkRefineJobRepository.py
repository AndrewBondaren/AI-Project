import uuid
from datetime import datetime, timezone

from app.db.database import Database
from app.db.models.chunkRefineJob import ChunkRefineJob
from app.db.repositories.iChunkRefineJobRepository import IChunkRefineJobRepository
from app.db.repositories.sqlite.base import BaseRepository


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteChunkRefineJobRepository(BaseRepository[ChunkRefineJob], IChunkRefineJobRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, ChunkRefineJob)

    async def upsert(self, job: ChunkRefineJob) -> None:
        await super().upsert(job)

    async def has_pending(self, world_uid: str, gx: int, gy: int, cx: int, cy: int) -> bool:
        sql = (
            "SELECT 1 FROM chunk_refine_jobs WHERE world_uid = ? AND gx = ? AND gy = ? "
            "AND cx = ? AND cy = ? AND status = 'pending' LIMIT 1"
        )
        async with self._db.conn.execute(sql, [world_uid, gx, gy, cx, cy]) as cur:
            row = await cur.fetchone()
        return row is not None

    async def pop_next_pending(self, world_uid: str) -> ChunkRefineJob | None:
        sql = (
            "SELECT * FROM chunk_refine_jobs WHERE world_uid = ? AND status = 'pending' "
            "ORDER BY priority ASC, created_at ASC LIMIT 1"
        )
        async with self._db.conn.execute(sql, [world_uid]) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        from app.db.mapper import from_row
        job = from_row(ChunkRefineJob, row)
        job.status = "running"
        job.updated_at = _utc_now()
        await self.save(job)
        return job

    async def mark_complete(self, job_uid: str, *, content_hash: str | None = None) -> None:
        sql = (
            "UPDATE chunk_refine_jobs SET status = 'complete', content_hash = ?, updated_at = ? "
            "WHERE job_uid = ?"
        )
        await self._db.conn.execute(sql, [content_hash, _utc_now(), job_uid])
        await self._db.conn.commit()


def new_chunk_refine_job(
    world_uid: str,
    gx: int,
    gy: int,
    cx: int,
    cy: int,
    *,
    priority: float,
) -> ChunkRefineJob:
    now = _utc_now()
    return ChunkRefineJob(
        job_uid=str(uuid.uuid4()),
        world_uid=world_uid,
        gx=gx,
        gy=gy,
        cx=cx,
        cy=cy,
        status="pending",
        priority=priority,
        content_hash=None,
        created_at=now,
        updated_at=now,
    )
