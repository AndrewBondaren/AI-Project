"""SQLite implementation of ``IReliefTemplateRepository``."""

from __future__ import annotations

from app.db.database import Database
from app.db.models.reliefTemplate import ReliefTemplateRow
from app.db.repositories.iReliefTemplateRepository import IReliefTemplateRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteReliefTemplateRepository(BaseRepository[ReliefTemplateRow], IReliefTemplateRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, ReliefTemplateRow)

    async def get_by_uid(self, template_uid: str) -> ReliefTemplateRow | None:
        return await self.fetch_one("template_uid = ?", [template_uid])

    async def get_by_system_name(self, system_name: str) -> ReliefTemplateRow | None:
        return await self.fetch_one("system_name = ?", [system_name])

    async def list_all(self) -> list[ReliefTemplateRow]:
        return await self.fetch_all("1=1", [], order="system_name ASC")

    async def list_by_context(self, context: str) -> list[ReliefTemplateRow]:
        return await self.fetch_all("context = ?", [context], order="system_name ASC")

    async def upsert(self, row: ReliefTemplateRow) -> None:
        await super().upsert(row)

    async def delete(self, template_uid: str) -> None:
        await super().delete(template_uid)
