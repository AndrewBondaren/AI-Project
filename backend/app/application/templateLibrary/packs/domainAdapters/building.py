"""Strict building member bodies; unrepresentable wire fields reject."""

from app.application.templateLibrary.packs.domainAdapters.bodyPreparation import TemplateBodyPreparation
from app.application.templateLibrary.packs.domainAdapters.templateBodyAdapter import TemplateBodyAdapter
from app.dataModel.locations.structure.building.buildingTemplate import BuildingTemplate
from app.ids import LibraryKind


class BuildingBodyPreparation(TemplateBodyPreparation[BuildingTemplate]):
    library_kind = LibraryKind.BUILDING_TEMPLATES
    model = BuildingTemplate


class BuildingPackAdapter(TemplateBodyAdapter):
    library_kind = LibraryKind.BUILDING_TEMPLATES
    preparation = BuildingBodyPreparation()

    def __init__(self, library):
        self._library = library
