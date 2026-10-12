"""Relief domain adapter — name-keyed bodies + ``relief_template_registry``
pointers + ``relief_pick_policy`` world-side ref field (TZ §0.2/§2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import ClassVar

from app.application.jsonValidation.resolve import resolve_model
from app.application.worldData.libraryPacks.domainAdapters.contract import (
    PackDomainAdapter,
    RemappedMember,
)
from app.application.worldData.libraryPacks.domainAdapters.mixins import (
    _LibraryBodyMixin,
    _RegistryPointerMixin,
)
from app.application.worldData.libraryPacks.domainAdapters.remapRefs import (
    _remap_relief_pick_policy,
)
from app.application.worldData.libraryPacks.domainAdapters.refFields import relief_policy_refs
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.libraryPacks.lifecycleContracts import FallbackDecision
from app.application.worldData.reliefErrors import ReliefValidationError
from app.application.worldData.reliefGeomWarn import warn_template_invalid_geom
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.worldData.reliefTerrainSync import (
    merge_missing_terrain_entries,
)
from app.application.worldData.reliefWorldImportService import ReliefWorldImportService
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.reliefTemplateRegistryEntry import (
    ReliefTemplateRegistryEntry,
)
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository
from app.ids import LibraryKind


class ReliefPackAdapter(_RegistryPointerMixin, _LibraryBodyMixin, PackDomainAdapter):
    """Name-keyed relief bodies; ``relief_template_registry`` pointers."""

    library_kind = LibraryKind.RELIEF_TEMPLATES
    registry_field: ClassVar[str] = "relief_template_registry"

    def __init__(
        self,
        library: ReliefTemplateLibraryService,
        world_repository: IWorldRepository,
        world_import: ReliefWorldImportService | None = None,
    ) -> None:
        self._library = library
        self._world_repo = world_repository
        self._world_import = world_import

    def prepare_body(
        self,
        raw: dict,
        *,
        local_uid: str,
        template_uid: str,
        world: World | None = None,
    ) -> ReliefTemplate:
        if not isinstance(raw, dict):
            raise LibraryPackValidationError(
                f"relief body for '{local_uid}' must be a JSON object"
            )
        try:
            if world is not None and self._world_import is not None:
                outline = self._world_import.prepare_body(world, raw)  # warns geom
            else:
                outline = resolve_model(ReliefTemplate, raw, label=local_uid)
                warn_template_invalid_geom(outline)
        except (ValueError, ReliefValidationError) as exc:
            raise LibraryPackValidationError(str(exc)) from exc
        if outline.system_name != local_uid:
            raise LibraryPackValidationError(
                f"relief body system_name '{outline.system_name}' != "
                f"member local_uid '{local_uid}'"
            )
        return outline


    def world_refs(self, world):
        return relief_policy_refs(world)

    def resolve_fallback(self, *, world_uid):
        """R21 unresolved policy: no template substitution — reject (TZ §5)."""
        return FallbackDecision.rejected()


    def _pointer_entry(
        self, member: LibraryPackMemberRow, outline: ReliefTemplate
    ) -> ReliefTemplateRegistryEntry:
        return self.pointer_entry(member, outline).model_copy(
            update={"imported_at": datetime.now(timezone.utc).isoformat()})

    def pointer_entry(self, member, outline):
        return ReliefTemplateRegistryEntry(system_template_uid=member.template_uid,
                                           display_template_name=outline.display_name, context=outline.context)

    def remap_body(self, body, *, template_uid, uid_map, local_uid=None):
        from app.application.worldData.libraryPacks.domainAdapters.contract import _SYSTEM_NAME_FIELD
        result = dict(body)
        if local_uid is not None:
            result[_SYSTEM_NAME_FIELD] = local_uid
        return result

    def prepare_world_refs(self, world, uid_map, members, *, removed_uids=()):
        from app.application.worldData.reliefTerrainSync import missing_terrain_entries
        result = super().prepare_world_refs(world, uid_map, members, removed_uids=removed_uids)
        policy = _remap_relief_pick_policy(result, uid_map)
        if policy is not None:
            result.relief_pick_policy = policy
        needed = (c.terrain.value for rm in members if isinstance(rm.outline, ReliefTemplate)
                  for c in rm.outline.conditions)
        entries = missing_terrain_entries(result, needed)
        if entries:
            result.terrain_registry = list(result.terrain_registry or []) + [e.model_dump(mode="json") for e in entries]
        return result

    async def remap_world_refs(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> None:
        self._rebuild_registry_field(world, uid_map, members)
        policy = _remap_relief_pick_policy(world, uid_map)
        if policy is not None:
            world.relief_pick_policy = policy
        for rm in members:
            if not isinstance(rm.outline, ReliefTemplate):
                continue
            merge_missing_terrain_entries(
                world,
                (c.terrain.value for c in rm.outline.conditions),
                source="pack_instantiate",
                template_uid=rm.member.template_uid,
                system_name=rm.outline.system_name,
            )
        await self._world_repo.update(world)
