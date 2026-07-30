from app.db.database import Database
from app.db.models.buildingTemplate import BuildingTemplateRow
from app.db.repositories.iBuildingTemplateRepository import IBuildingTemplateRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteBuildingTemplateRepository(
    BaseRepository[BuildingTemplateRow], IBuildingTemplateRepository,
):

    def __init__(self, db: Database) -> None:
        super().__init__(db, BuildingTemplateRow)

    async def get_by_uid(self, template_uid: str) -> BuildingTemplateRow | None:
        return await self.fetch_one("template_uid = ?", [template_uid])

    async def list_all(self) -> list[BuildingTemplateRow]:
        return await self.fetch_all("1=1", [], order="system_name ASC")

    async def upsert(self, row: BuildingTemplateRow) -> None:
        await super().upsert(row)

    async def delete(self, template_uid: str) -> None:
        await super().delete(template_uid)
