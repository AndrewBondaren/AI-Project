"""Plot body repository over the shared mapper/transaction boundary."""

from app.db.database import Database
from app.db.models.plotTemplate import PlotTemplateRow
from app.db.repositories.iPlotTemplateRepository import IPlotTemplateRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqlitePlotTemplateRepository(BaseRepository[PlotTemplateRow], IPlotTemplateRepository):
    def __init__(self, db: Database) -> None:
        super().__init__(db, PlotTemplateRow)

    async def get_by_uid(self, template_uid: str) -> PlotTemplateRow | None:
        return await self.fetch_one("template_uid = ?", [template_uid])

    async def list_all(self) -> list[PlotTemplateRow]:
        """Administrative listing; world availability is resolved by the catalog."""
        return await self.fetch_all(order="template_uid ASC")
