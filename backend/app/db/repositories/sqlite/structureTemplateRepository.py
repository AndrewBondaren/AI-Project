"""SQLite implementation of ``IStructureTemplateRepository``."""

from __future__ import annotations

from app.db.database import Database
from app.db.models.structureTemplate import StructureTemplateRow
from app.db.repositories.iStructureTemplateRepository import IStructureTemplateRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteStructureTemplateRepository(
    BaseRepository[StructureTemplateRow], IStructureTemplateRepository,
):

    def __init__(self, db: Database) -> None:
        super().__init__(db, StructureTemplateRow)

    async def get_by_uid(self, template_uid: str) -> StructureTemplateRow | None:
        return await self.fetch_one("template_uid = ?", [template_uid])

    async def list_all(self) -> list[StructureTemplateRow]:
        return await self.fetch_all("1=1", [], order="display_name ASC")

    async def upsert(self, row: StructureTemplateRow) -> None:
        await super().upsert(row)

    async def delete(self, template_uid: str) -> None:
        await super().delete(template_uid)
