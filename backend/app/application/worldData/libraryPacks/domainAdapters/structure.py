"""Structure domain adapter — model-A bodies whose wire ``system_name``
IS the member uid; world-side refs live in plot-layout rows (TZ §0.2/§2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.application.worldData.libraryPacks.domainAdapters.contract import (
    _SYSTEM_NAME_FIELD,
    PackDomainAdapter,
    RemappedMember,
)
from app.application.worldData.libraryPacks.domainAdapters.mixins import _LibraryBodyMixin
from app.application.worldData.libraryPacks.domainAdapters.remapRefs import (
    _remap_structure_refs,
)
from app.application.worldData.structureTemplateLibraryService import (
    StructureTemplateLibraryService,
)
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository
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
    the 4c referenced-set. World-side refs to structure members live in
    plot-layout rows of ``building_template_registry``.
    """

    library_kind = LibraryKind.STRUCTURE_TEMPLATES

    def __init__(
        self,
        library: StructureTemplateLibraryService,
        world_repository: IWorldRepository,
    ) -> None:
        self._library = library
        self._world_repo = world_repository

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

    def world_refs(self, world):
        # Explicit transitional world format, removed with registry cutover (B6).
        from app.application.worldData.libraryPacks.domainAdapters.refFields import structure_refs
        return tuple(ref for i, row in enumerate(world.building_template_registry or [])
                     for ref in structure_refs(row,
                         f"world:{world.world_uid}:building_template_registry[{i}]"))

    def prepare_world_refs(self, world, uid_map, members, *, removed_uids=()):
        from copy import deepcopy
        from app.application.worldData.libraryPacks.domainAdapters.remapRefs import remap_pins
        result = deepcopy(world)
        remap_pins(result, uid_map)
        result.building_template_registry = [
            _remap_structure_refs(row, uid_map) or row if isinstance(row, dict) else row
            for row in result.building_template_registry or []]
        return result

    async def remap_world_refs(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> None:
        """World-side refs to structure members — ``structure`` keys
        inside plot-layout rows of ``building_template_registry``."""
        raw = world.building_template_registry or []
        out: list = []
        from app.application.worldData.libraryPacks.domainAdapters.remapRefs import remap_pins
        changed = remap_pins(world, uid_map)
        for row in raw:
            remapped = (
                _remap_structure_refs(row, uid_map) if isinstance(row, dict) else None
            )
            out.append(remapped if remapped is not None else row)
            changed = changed or remapped is not None
        if changed:
            world.building_template_registry = out
            await self._world_repo.update(world)
