"""Template-library wiring: pack catalog, adapters, library services."""

from app.application.templateLibrary.reliefTemplateLibraryService import ReliefTemplateLibraryService
from app.application.templateLibrary.buildingTemplateLibraryService import BuildingTemplateLibraryService
from app.application.templateLibrary.packs.packCatalog import PackCatalogRepos
from app.application.templateLibrary.packs.domainAdapters import PackDomainAdapter
from app.application.templateLibrary.packs.effectiveCatalog import EffectiveCatalogLoader
from app.application.templateLibrary.packs.refResolve import RefResolver
from app.ids import LibraryKind
from app.application.templateLibrary.packs.domainAdapters.factory import (
    build_pack_domain_adapters,
)
from app.application.templateLibrary.packs.packService import LibraryPackService
from app.application.templateLibrary.structureTemplateLibraryService import (
    StructureTemplateLibraryService,
)


class TemplateLibraryWiring:
    """Pack catalog, domain adapters and per-domain library services."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._relief_template_library_service: ReliefTemplateLibraryService | None = None
        self._building_template_library_service: BuildingTemplateLibraryService | None = None
        self._structure_template_library_service: StructureTemplateLibraryService | None = None
        self._library_pack_service: LibraryPackService | None = None
        self._pack_domain_adapters: dict[LibraryKind, PackDomainAdapter] | None = None
        self._effective_catalog_loader: EffectiveCatalogLoader | None = None
        self._ref_resolver: RefResolver | None = None

    def relief_template_library_service(self) -> ReliefTemplateLibraryService:
        if self._relief_template_library_service is None:
            self._relief_template_library_service = ReliefTemplateLibraryService(
                repo=self.relief_template_repository(),
                db=self._db,
                write_provider=self.library_pack_service,
                catalog=PackCatalogRepos(
                    packs=self.library_pack_repository(),
                    members=self.library_pack_member_repository(),
                    deps=self.library_pack_dependency_repository(),
                ),
            )
        return self._relief_template_library_service

    def building_template_library_service(self) -> BuildingTemplateLibraryService:
        if self._building_template_library_service is None:
            self._building_template_library_service = BuildingTemplateLibraryService(
                repo=self.building_template_repository(),
                db=self._db,
                write_provider=self.library_pack_service,
                ensure_provider=self.ensure_template_canonical,
            )
        return self._building_template_library_service

    def structure_template_library_service(self) -> StructureTemplateLibraryService:
        if self._structure_template_library_service is None:
            self._structure_template_library_service = StructureTemplateLibraryService(
                repo=self.structure_template_repository(),
                db=self._db,
                write_provider=self.library_pack_service,
                ensure_provider=self.ensure_template_canonical,
                catalog=PackCatalogRepos(
                    packs=self.library_pack_repository(),
                    members=self.library_pack_member_repository(),
                    deps=self.library_pack_dependency_repository(),
                ),
            )
        return self._structure_template_library_service

    def pack_catalog_repos(self) -> PackCatalogRepos:
        """Full pack catalog bundle (packs + members + deps) — public read seam."""
        return PackCatalogRepos(
            packs=self.library_pack_repository(),
            members=self.library_pack_member_repository(),
            deps=self.library_pack_dependency_repository(),
        )

    def pack_domain_adapters(self) -> dict[LibraryKind, PackDomainAdapter]:
        if self._pack_domain_adapters is None:
            self._pack_domain_adapters = build_pack_domain_adapters(
                relief_library=self.relief_template_library_service(),
                structure_library=self.structure_template_library_service(),
                building_library=self.building_template_library_service(),
                plot_library=self.plot_template_library_service(),
            )
        return self._pack_domain_adapters

    def library_pack_service(self) -> LibraryPackService:
        """Step-4a CRUD boundary over packs/members (membership-only, B6)."""
        if self._library_pack_service is None:
            self._library_pack_service = LibraryPackService(
                db=self._db,
                packs=self.library_pack_repository(),
                members=self.library_pack_member_repository(),
                deps=self.library_pack_dependency_repository(),
                world_service=self.world_service(),
                adapters=self.pack_domain_adapters(),
                write_service=self.library_write_service(),
                locations=self.location_repository(),
            )
        return self._library_pack_service

    def library_write_service(self):
        from app.application.templateLibrary.packs.write.writeServiceFactory import build_library_write_service
        return build_library_write_service(db=self._db, catalog=self.pack_catalog_repos(),
            adapters=self.pack_domain_adapters(), worlds=self.world_service(), world_repository=self.world_repository(),
            locations=self.location_repository())

    def effective_catalog_loader(self) -> EffectiveCatalogLoader:
        """Step-5a runtime read facade — membership-scoped world catalog."""
        if self._effective_catalog_loader is None:
            self._effective_catalog_loader = EffectiveCatalogLoader(
                self.pack_catalog_repos(), self.pack_domain_adapters(),
                ensure_defaults=self.ensure_template_canonical,
            )
        return self._effective_catalog_loader

    def template_snapshot_loader(self):
        """B3 async boundary: world template snapshot for packing."""
        from app.application.templateLibrary.templateSnapshotLoader import (
            TemplateSnapshotLoader,
        )
        if getattr(self, "_template_snapshot_loader", None) is None:
            self._template_snapshot_loader = TemplateSnapshotLoader(
                self.effective_catalog_loader(),
            )
        return self._template_snapshot_loader

    def ref_resolver(self) -> RefResolver:
        """Step-5a template-ref resolve (TZ packs §5) over the effective catalog."""
        if self._ref_resolver is None:
            self._ref_resolver = RefResolver(
                self.pack_catalog_repos(), self.pack_domain_adapters()
            )
        return self._ref_resolver


