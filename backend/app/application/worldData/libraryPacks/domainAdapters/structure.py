"""Structure domain adapter — model-A bodies whose wire ``system_name``
IS the member uid (TZ §0.2/§2)."""

from __future__ import annotations

from collections.abc import Mapping

from app.application.worldData.libraryPacks.domainAdapters.contract import (
    _SYSTEM_NAME_FIELD,
    PackDomainAdapter,
)
from app.application.worldData.libraryPacks.domainAdapters.mixins import _LibraryBodyMixin
from app.application.worldData.libraryPacks.domainAdapters.remapRefs import remap_pins
from app.application.worldData.structureTemplateLibraryService import (
    StructureTemplateLibraryService,
)
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.db.models.world import World
from app.ids import LibraryKind
from app.application.worldData.libraryPacks.domainAdapters.bodyPreparation import TemplateBodyPreparation


class StructureBodyPreparation(TemplateBodyPreparation[StructureTemplate]):
    library_kind = LibraryKind.STRUCTURE_TEMPLATES
    model = StructureTemplate
    model_a = True

    def remap_body(self, body, uid_map):
        target = uid_map.get(str(body.system_name))
        return body.model_copy(update={_SYSTEM_NAME_FIELD: target}) if target else body


class StructurePackAdapter(_LibraryBodyMixin, PackDomainAdapter):
    """Model-A structures: wire ``system_name`` IS the member uid.

    No world registry exists for structures — the member is reachable
    through pack membership; body refs (``main_building.structure``) are
    the 4c referenced-set.
    """

    library_kind = LibraryKind.STRUCTURE_TEMPLATES

    def __init__(self, library: StructureTemplateLibraryService) -> None:
        self._library = library

    def prepare_body(
        self,
        raw: dict,
        *,
        local_uid: str,
        template_uid: str,
        world: World | None = None,
    ) -> StructureTemplate:
        return StructureBodyPreparation().prepare_body(raw, local_uid=local_uid,
            template_uid=template_uid, world=world)


    def remap_body(
        self, body: dict, *, template_uid: str, uid_map: Mapping[str, str], local_uid: str | None = None,
    ) -> dict:
        """Model A: the copied body embeds its new member uid (TZ §2)."""
        out = dict(body)
        out[_SYSTEM_NAME_FIELD] = template_uid
        return out

    def prepare_world_refs(self, world, uid_map, members):
        from copy import deepcopy
        result = deepcopy(world)
        remap_pins(result, uid_map)
        return result
