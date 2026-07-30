"""Build ordered bundle section handlers — tz_world_bundle.md."""

from __future__ import annotations

from app.application.worldData.bundle.entity.sections import (
    ConnectionEdgesSectionHandler,
    ConnectionNodesSectionHandler,
    LocationsSectionHandler,
    StatesSectionHandler,
    WorldSectionHandler,
)
from app.application.worldData.bundle.handler import IBundleSectionHandler
from app.application.worldData.bundle.library.libraryTemplateSection import (
    LibrarySectionAdapter,
    LibraryTemplateSectionHandler,
)
from app.application.worldData.bundle.order import BUNDLE_IMPORT_ORDER
from app.application.worldData.bundle.reliefSection import (
    export_relief_template_bodies,
    import_relief_templates_section,
)
from app.application.worldData.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.application.worldData.connectionGraphService import ConnectionGraphService
from app.application.worldData.namedLocationService import NamedLocationService
from app.application.worldData.raceService import RaceService
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.worldData.reliefWorldImportService import ReliefWorldImportService
from app.application.worldData.stateService import StateService
from app.application.worldData.worldPerkService import WorldPerkService
from app.application.worldData.worldService import WorldService
from app.dataModel.worldBundle.bundleSections import BundleSection


def build_bundle_handlers(
    *,
    world_service: WorldService,
    state_service: StateService,
    location_service: NamedLocationService,
    connection_graph_service: ConnectionGraphService,
    race_service: RaceService,
    perk_service: WorldPerkService,
    relief_library: ReliefTemplateLibraryService,
    relief_import: ReliefWorldImportService,
    building_library: BuildingTemplateLibraryService,
) -> list[IBundleSectionHandler]:
    async def _export_relief(world_uid: str) -> list[dict]:
        world = await world_service.get_by_id(world_uid)
        return await export_relief_template_bodies(world, relief_library)

    by_key: dict[str, IBundleSectionHandler] = {
        BundleSection.WORLD: WorldSectionHandler(world_service),
        BundleSection.STATES: StatesSectionHandler(state_service),
        BundleSection.LOCATIONS: LocationsSectionHandler(location_service),
        BundleSection.CONNECTION_NODES: ConnectionNodesSectionHandler(
            connection_graph_service,
        ),
        BundleSection.CONNECTION_EDGES: ConnectionEdgesSectionHandler(
            connection_graph_service,
        ),
        BundleSection.RELIEF_TEMPLATES: LibraryTemplateSectionHandler(
            LibrarySectionAdapter(
                section_key=BundleSection.RELIEF_TEMPLATES,
                export_bodies=_export_relief,
                import_bodies=lambda wid, bodies: import_relief_templates_section(
                    wid, bodies, relief_import,
                ),
            ),
        ),
        BundleSection.BUILDING_TEMPLATES: LibraryTemplateSectionHandler(
            LibrarySectionAdapter(
                section_key=BundleSection.BUILDING_TEMPLATES,
                export_bodies=building_library.export_bodies_for_world,
                import_bodies=building_library.import_bodies_into_world,
            ),
        ),
        BundleSection.RACE_TEMPLATES: LibraryTemplateSectionHandler(
            LibrarySectionAdapter(
                section_key=BundleSection.RACE_TEMPLATES,
                export_bodies=race_service.export_bodies_for_world,
                import_bodies=race_service.import_bodies,
            ),
        ),
        BundleSection.PERK_TEMPLATES: LibraryTemplateSectionHandler(
            LibrarySectionAdapter(
                section_key=BundleSection.PERK_TEMPLATES,
                export_bodies=perk_service.export_bodies_for_world,
                import_bodies=perk_service.import_bodies,
            ),
        ),
    }
    return [by_key[k] for k in BUNDLE_IMPORT_ORDER]
