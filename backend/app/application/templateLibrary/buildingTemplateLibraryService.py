"""Building template library — tz_building_generator §5–6 / WB-11.

Membership is the single availability source (B6/B7): world-owned member
writes never touch legacy ``worlds`` registry columns.
"""

from __future__ import annotations

from app.ids import LibraryKind, library_uid
from app.db.database import Database
from app.db.models.buildingTemplate import BuildingTemplateRow
from app.db.repositories.iBuildingTemplateRepository import IBuildingTemplateRepository
from app.dataModel.locations.structure.building.buildingTemplate import BuildingTemplate


def building_template_uid(system_name: str) -> str:
    return library_uid(LibraryKind.BUILDING_TEMPLATES, system_name)


class BuildingTemplateLibraryService:

    def __init__(
        self,
        repo: IBuildingTemplateRepository,
        *,
        db: Database | None = None,
        write_provider=None,
        ensure_provider=None,
    ) -> None:
        self._repo = repo
        self._db = db
        self._write_provider = write_provider
        self._ensure_provider = ensure_provider

    async def get_by_uid(self, template_uid: str) -> BuildingTemplateRow | None:
        if self._ensure_provider is not None:
            await self._ensure_provider()
        return await self.find_by_uid(template_uid)

    async def list_all(self) -> list[BuildingTemplateRow]:
        if self._ensure_provider is not None:
            await self._ensure_provider()
        return await self._repo.list_all()

    async def find_by_uid(self, template_uid: str) -> BuildingTemplateRow | None:
        return await self._repo.get_by_uid(template_uid)

    async def write_body(self, body: BuildingTemplate, *, pack_uid, template_uid=None,
                         source_file=None, world_uid=None) -> BuildingTemplateRow:
        from app.application.worldData.libraryPacks.domainWriteEntry import write_domain_body
        return await write_domain_body(self._write_provider(), LibraryKind.BUILDING_TEMPLATES,
            body, pack_uid=pack_uid, template_uid=template_uid,
            source_file=source_file, world_uid=world_uid)

    async def persist_prepared(self, outline, *, template_uid, source_file, added):
        from app.application.worldData.libraryPacks.preparedPersistence import persist_body_row
        row = BuildingTemplateRow(template_uid=template_uid, system_name=outline.system_name,
            display_name=outline.display_name,
            data=outline.model_dump(mode="json"), source_file=source_file)
        return await persist_body_row(self._repo, row, added=added)

    async def delete_prepared(self, template_uid: str) -> None:
        from app.db.database import _in_transaction
        if not _in_transaction.get():
            raise RuntimeError("prepared deletion requires caller UOW")
        await self._repo.delete(template_uid)

    async def delete(self, template_uid: str, *, world_uid=None) -> None:
        if self._write_provider is not None:
            await self._write_provider().delete_member(template_uid, world_uid=world_uid)
            return
        if self._db is not None:
            raise RuntimeError("SQL library writes require the common write service")
        await self._repo.delete(template_uid)
