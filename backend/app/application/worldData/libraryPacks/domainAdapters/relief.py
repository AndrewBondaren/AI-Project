"""Relief domain adapter — name-keyed bodies + ``relief_template_registry``
pointers + ``relief_pick_policy`` world-side ref field (TZ §0.2/§2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

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
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository
from app.ids import LibraryKind

if TYPE_CHECKING:
    from app.application.worldData.reliefTemplateFsImport import ReliefPackImport


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

    async def write_body(self, raw, *, local_uid, template_uid, pack, world,
                         source_file=None):
        outline = self.prepare_body(raw, local_uid=local_uid, template_uid=template_uid, world=world)
        await self._library.upsert_outline(outline, source_file=source_file,
                                          pack_uid=pack.pack_uid, template_uid=template_uid)
        return outline

    def world_refs(self, world):
        return relief_policy_refs(world)

    async def import_fs_pack(
        self, path: str | Path, *, domain_root: Path | None = None
    ) -> ReliefPackImport:
        from app.application.worldData.reliefTemplateFsImport import import_relief_path

        return await import_relief_path(
            path,
            upsert_from_dict=self._library.upsert_from_dict,
            domain_root=domain_root,
        )

    def _pointer_entry(
        self, member: LibraryPackMemberRow, outline: ReliefTemplate
    ) -> ReliefTemplateRegistryEntry:
        return ReliefTemplateRegistryEntry(
            system_template_uid=member.template_uid,
            display_template_name=outline.display_name,
            context=outline.context,
            imported_at=datetime.now(timezone.utc).isoformat(),
        )

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
