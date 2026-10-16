"""Build ordered bundle section handlers — tz_world_bundle.md."""

from __future__ import annotations

from app.application.worldBundle.entity.sections import (
    ConnectionEdgesSectionHandler,
    ConnectionNodesSectionHandler,
    LocationsSectionHandler,
    StatesSectionHandler,
    WorldSectionHandler,
)
from app.application.worldBundle.handler import IBundleSectionHandler
from app.application.worldBundle.library.libraryTemplateSection import (
    LibrarySectionAdapter,
    LibraryTemplateSectionHandler,
)
from app.application.worldBundle.order import BUNDLE_IMPORT_ORDER
from app.application.worldBundle.connectionGraphService import ConnectionGraphService
from app.application.worldData.namedLocationService import NamedLocationService
from app.application.worldData.raceService import RaceService
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
) -> list[IBundleSectionHandler]:

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
        BundleSection.RACE_TEMPLATES: LibraryTemplateSectionHandler(
            LibrarySectionAdapter(
                section_key=BundleSection.RACE_TEMPLATES,
                export_bodies=race_service.export_bodies_for_world,
                import_bodies=race_service.import_bodies,
                prepare_body=lambda world, row, *, ctx=None: race_service.prepare_body(row, ctx=ctx),
            ),
        ),
        BundleSection.PERK_TEMPLATES: LibraryTemplateSectionHandler(
            LibrarySectionAdapter(
                section_key=BundleSection.PERK_TEMPLATES,
                export_bodies=perk_service.export_bodies_for_world,
                import_bodies=perk_service.import_bodies,
                prepare_body=lambda world, row, *, ctx=None: perk_service.prepare_body(row, ctx=ctx),
            ),
        ),
    }
    return [by_key[k] for k in BUNDLE_IMPORT_ORDER]
