"""Plot body storage; all public mutations delegate to the common pack writer."""

from app.application.worldData.libraryPacks.preparedPersistence import persist_body_row
from app.dataModel.locations.structure.building.plotTemplate import PlotTemplate
from app.db.database import _in_transaction
from app.db.models.plotTemplate import PlotTemplateRow
from app.db.repositories.iPlotTemplateRepository import IPlotTemplateRepository
from app.ids import LibraryKind


class PlotTemplateLibraryService:
    def __init__(self, repo: IPlotTemplateRepository, *, write_provider, ensure_provider=None):
        self._repo = repo
        self._write_provider = write_provider
        self._ensure_provider = ensure_provider

    async def get_by_uid(self, template_uid: str) -> PlotTemplateRow | None:
        if self._ensure_provider is not None:
            await self._ensure_provider()
        return await self.find_by_uid(template_uid)

    async def list_all(self) -> list[PlotTemplateRow]:
        if self._ensure_provider is not None:
            await self._ensure_provider()
        return await self._repo.list_all()

    async def find_by_uid(self, template_uid: str) -> PlotTemplateRow | None:
        return await self._repo.get_by_uid(template_uid)

    async def write_body(self, body: PlotTemplate, *, pack_uid, template_uid=None,
                         source_file=None, world_uid=None) -> PlotTemplateRow:
        from app.application.worldData.libraryPacks.domainWriteEntry import write_domain_body
        return await write_domain_body(self._write_provider(), LibraryKind.PLOT_TEMPLATES,
            body, pack_uid=pack_uid, template_uid=template_uid,
            source_file=source_file, world_uid=world_uid)

    async def delete(self, template_uid, *, world_uid=None):
        await self._write_provider().delete_member(template_uid, world_uid=world_uid)

    async def persist_prepared(self, body, *, template_uid, source_file, added):
        row = PlotTemplateRow(template_uid=template_uid, system_name=body.system_name,
            display_name=body.display_name, data=body.model_dump(mode="json"), source_file=source_file)
        return await persist_body_row(self._repo, row, added=added)

    async def delete_prepared(self, template_uid):
        if not _in_transaction.get():
            raise RuntimeError("prepared deletion requires caller UOW")
        await self._repo.delete(template_uid)
