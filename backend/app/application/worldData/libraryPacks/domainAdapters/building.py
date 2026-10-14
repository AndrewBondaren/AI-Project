"""Strict building member bodies; legacy outlines/plots require explicit conversion."""

from app.application.worldData.libraryPacks.domainAdapters.bodyPreparation import TemplateBodyPreparation
from app.application.worldData.libraryPacks.domainAdapters.templateBodyAdapter import TemplateBodyAdapter
from app.dataModel.locations.structure.building.buildingTemplate import BuildingTemplate
from app.ids import LibraryKind


class BuildingBodyPreparation(TemplateBodyPreparation[BuildingTemplate]):
    library_kind = LibraryKind.BUILDING_TEMPLATES
    model = BuildingTemplate


class BuildingPackAdapter(TemplateBodyAdapter):
    library_kind = LibraryKind.BUILDING_TEMPLATES
    preparation = BuildingBodyPreparation()

    def __init__(self, library, world_repository):
        self._library = library
