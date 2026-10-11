"""Structure domain adapter — model-A bodies whose wire ``system_name``
IS the member uid; world-side refs live in plot-layout rows (TZ §0.2/§2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from app.application.jsonValidation.resolve import resolve_model
from app.application.worldData.libraryPacks.domainAdapters.contract import (
    _SYSTEM_NAME_FIELD,
    PackDomainAdapter,
    RemappedMember,
)
from app.application.worldData.libraryPacks.domainAdapters.mixins import _LibraryBodyMixin
from app.application.worldData.libraryPacks.domainAdapters.remapRefs import (
    _remap_structure_refs,
)
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.structureTemplateLibraryService import (
    StructureTemplateLibraryService,
)
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository
from app.ids import LibraryKind

if TYPE_CHECKING:
    from app.application.worldData.structureTemplateFsImport import StructurePackImport


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
        if not isinstance(raw, dict):
            raise LibraryPackValidationError(
                f"structure body for '{local_uid}' must be a JSON object"
            )
        payload = dict(raw)
        if payload.get(_SYSTEM_NAME_FIELD) is None:
            payload[_SYSTEM_NAME_FIELD] = template_uid
        try:
            outline = resolve_model(StructureTemplate, payload, label=local_uid)
        except ValueError as exc:
            raise LibraryPackValidationError(str(exc)) from exc
        if str(outline.system_name) != template_uid:
            raise LibraryPackValidationError(
                f"structure body system_name '{outline.system_name}' != member "
                f"template_uid '{template_uid}' (model A: body carries the uid)"
            )
        return outline

    async def write_body(self, raw, *, local_uid, template_uid, pack, world,
                         source_file=None):
        outline = self.prepare_body(raw, local_uid=local_uid, template_uid=template_uid, world=world)
        await self._library.upsert_outline(outline, source_file=source_file)
        return outline

    def remap_body(
        self, body: dict, *, template_uid: str, uid_map: Mapping[str, str]
    ) -> dict:
        """Model A: the copied body embeds its new member uid (TZ §2)."""
        out = dict(body)
        out[_SYSTEM_NAME_FIELD] = template_uid
        return out

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

    async def import_fs_pack(
        self, path: str | Path, *, domain_root: Path | None = None
    ) -> StructurePackImport:
        from app.application.worldData.structureTemplateFsImport import (
            import_structure_templates_path,
        )

        return await import_structure_templates_path(
            path,
            upsert_from_dict=self._library.upsert_from_dict,
            domain_root=domain_root,
        )
