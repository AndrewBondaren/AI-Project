"""Lazy template storage providers, shared by the application container."""

from app.db.database import Database
from app.db.repositories.iBuildingTemplateRepository import IBuildingTemplateRepository
from app.db.repositories.iPlotTemplateRepository import IPlotTemplateRepository
from app.db.repositories.iStructureTemplateRepository import IStructureTemplateRepository
from app.db.repositories.sqlite.buildingTemplateRepository import SqliteBuildingTemplateRepository
from app.db.repositories.sqlite.plotTemplateRepository import SqlitePlotTemplateRepository
from app.db.repositories.sqlite.structureTemplateRepository import SqliteStructureTemplateRepository


class TemplateRepositoryProviders:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._plot_template_repository: IPlotTemplateRepository | None = None
        self._building_template_repository: IBuildingTemplateRepository | None = None
        self._structure_template_repository: IStructureTemplateRepository | None = None
        self._plot_template_library_service = None
        self._template_canonical_service = None

    async def ensure_template_canonical(self):
        from app.application.templateLibrary.packs.templateCanonicalService import TemplateCanonicalService
        if self._template_canonical_service is None:
            self._template_canonical_service = TemplateCanonicalService(
                db=self._db, catalog=self.pack_catalog_repos())
        return await self._template_canonical_service.ensure()

    def plot_template_library_service(self):
        from app.application.templateLibrary.plotTemplateLibraryService import PlotTemplateLibraryService
        if self._plot_template_library_service is None:
            self._plot_template_library_service = PlotTemplateLibraryService(
                self.plot_template_repository(), write_provider=self.library_pack_service,
                ensure_provider=self.ensure_template_canonical)
        return self._plot_template_library_service

    def plot_template_repository(self) -> IPlotTemplateRepository:
        if self._plot_template_repository is None:
            self._plot_template_repository = SqlitePlotTemplateRepository(self._db)
        return self._plot_template_repository

    def building_template_repository(self) -> IBuildingTemplateRepository:
        if self._building_template_repository is None:
            self._building_template_repository = SqliteBuildingTemplateRepository(db=self._db)
        return self._building_template_repository

    def structure_template_repository(self) -> IStructureTemplateRepository:
        if self._structure_template_repository is None:
            self._structure_template_repository = SqliteStructureTemplateRepository(db=self._db)
        return self._structure_template_repository
