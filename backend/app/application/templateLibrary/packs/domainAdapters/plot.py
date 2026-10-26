"""Plot domain preparation and common-writer adapter."""

from app.application.jsonValidation.worldRow import crops, livestock, resource_types
from app.application.jsonValidation.types import FieldPathError
from app.application.templateLibrary.packs.domainAdapters.bodyPreparation import (
    TemplateBodyPreparation, TemplatePreparationError,
)
from app.dataModel.locations.structure.building.plotTemplate import PlotTemplate
from app.ids import LibraryKind
from app.application.templateLibrary.packs.domainAdapters.templateBodyAdapter import TemplateBodyAdapter


class PlotBodyPreparation(TemplateBodyPreparation[PlotTemplate]):
    library_kind = LibraryKind.PLOT_TEMPLATES
    model = PlotTemplate

    def validate_world(self, body, world, path):
        super().validate_world(body, world, path)
        issues = []
        for resolver, kind in ((resource_types, body.resource_kind),
                               (crops, body.crop_kind), (livestock, body.livestock_kind)):
            if kind is None:
                continue
            registry = resolver(world)
            issues.extend(FieldPathError(path + ('subjects',),
                f'{code}: subject {token!r}', code=code)
                for token, code in registry.check_template_subjects(kind, body.subjects))
        if issues:
            raise TemplatePreparationError(tuple(issues))


class PlotPackAdapter(TemplateBodyAdapter):
    library_kind = LibraryKind.PLOT_TEMPLATES
    preparation = PlotBodyPreparation()

    def __init__(self, library):
        self._library = library
