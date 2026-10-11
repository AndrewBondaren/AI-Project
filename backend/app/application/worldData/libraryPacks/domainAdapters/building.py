"""Building domain adapter — name-keyed bodies +
``building_template_registry`` pointers; world-owned bodies pass
subject checks against resource/crops/livestock registries (TZ §0.2/§2)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, ClassVar

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.application.worldData.libraryPacks.domainAdapters.contract import (
    PackDomainAdapter,
)
from app.application.worldData.libraryPacks.domainAdapters.mixins import (
    _LibraryBodyMixin,
    _RegistryPointerMixin,
)
from app.application.worldData.libraryPacks.domainAdapters.remapRefs import (
    _remap_structure_refs,
)
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.dataModel.locations.structure.building.buildingTemplateOutline import (
    BuildingTemplateOutline,
)
from app.dataModel.locations.structure.building.buildingTemplateRegistryEntry import (
    BuildingTemplateRegistryEntry,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository
from app.ids import LibraryKind


class BuildingPackAdapter(_RegistryPointerMixin, _LibraryBodyMixin, PackDomainAdapter):
    """Name-keyed building bodies; ``building_template_registry`` pointers.

    World-owned bodies additionally pass the subject checks against the
    owning world's resource/crops/livestock registries.
    """

    library_kind = LibraryKind.BUILDING_TEMPLATES
    registry_field: ClassVar[str] = "building_template_registry"

    def __init__(
        self,
        library: BuildingTemplateLibraryService,
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
    ) -> BuildingTemplateOutline | PlotLayoutTemplate:
        if not isinstance(raw, dict):
            raise LibraryPackValidationError(
                f"building body for '{local_uid}' must be a JSON object"
            )
        ctx = ResolveContext(path_prefix=("building_templates", local_uid))
        try:
            body = self._library.parse_body(raw, ctx=ctx)
        except ValueError as exc:
            raise LibraryPackValidationError(str(exc)) from exc
        if world is not None:
            issues = self._library.subject_issues(world, body)
            if issues:
                token, code = issues[0]
                raise LibraryPackValidationError(
                    f"{local_uid}: {code}: extract/farm/livestock subject {token!r}"
                )
        if str(body.system_name) != local_uid:
            raise LibraryPackValidationError(
                f"building body system_name '{body.system_name}' != "
                f"member local_uid '{local_uid}'"
            )
        return body

    async def write_body(self, raw, *, local_uid, template_uid, pack, world,
                         source_file=None):
        body = self.prepare_body(raw, local_uid=local_uid, template_uid=template_uid, world=world)
        await self._library.upsert_outline(body, source_file=source_file,
                                          pack_uid=pack.pack_uid, template_uid=template_uid)
        return body

    def body_refs(self, body, consumer):
        from app.application.worldData.libraryPacks.domainAdapters.refFields import structure_refs
        return structure_refs(body, consumer)

    def world_refs(self, world):
        from app.application.worldData.libraryPacks.domainAdapters.refFields import structure_refs
        return tuple(ref for i, row in enumerate(world.building_template_registry or [])
                     if isinstance(row, dict) and 'system_template_uid' not in row
                     for ref in structure_refs(row, f"world:{world.world_uid}:building_template_registry[{i}]"))

    def remap_body(
        self, body: dict, *, template_uid: str, uid_map: Mapping[str, str]
    ) -> dict:
        """Plot layouts carry ``structure`` refs into the structure
        library — internal refs to source members follow the map (TZ §2)."""
        remapped = _remap_structure_refs(body, uid_map)
        return remapped if remapped is not None else dict(body)

    def _pointer_entry(
        self,
        member: LibraryPackMemberRow,
        outline: BuildingTemplateOutline | PlotLayoutTemplate,
    ) -> BuildingTemplateRegistryEntry:
        return BuildingTemplateRegistryEntry(
            system_template_uid=member.template_uid,
            display_template_name=outline.display_name,
            imported_at=datetime.now(timezone.utc).isoformat(),
        )
