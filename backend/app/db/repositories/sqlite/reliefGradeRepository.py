"""SQLite relief grade instances/systems."""

from __future__ import annotations

from app.db.database import Database
from app.db.models.reliefGradeInstance import ReliefGradeInstanceRow
from app.db.models.reliefGradeSystem import ReliefGradeSystemRow
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteReliefGradeRepository(IReliefGradeRepository):
    def __init__(self, db: Database) -> None:
        self._instances = BaseRepository(db, ReliefGradeInstanceRow)
        self._systems = BaseRepository(db, ReliefGradeSystemRow)
        self._db = db

    async def upsert_instance(self, row: ReliefGradeInstanceRow) -> None:
        await self._instances.upsert(row)

    async def upsert_system(self, row: ReliefGradeSystemRow) -> None:
        await self._systems.upsert(row)

    async def list_instances_for_world(self, world_uid: str) -> list[ReliefGradeInstanceRow]:
        return await self._instances.fetch_all(
            where="world_uid = ?",
            params=[world_uid],
        )

    async def delete_instances_for_world(self, world_uid: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM relief_grade_instances WHERE world_uid = ?",
            [world_uid],
        )
        await self._db.conn.execute(
            "DELETE FROM relief_grade_systems WHERE world_uid = ?",
            [world_uid],
        )
        await self._db.conn.commit()
