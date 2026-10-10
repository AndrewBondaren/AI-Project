"""Domain adapters of the pack application service — plan steps 4a–4b,
TZ §0.2/§2.

The universal pack layer (``packService``) owns identity, ownership and
atomicity; each adapter owns the body model, domain restrictions and the
transitional pointer dual-write: registry pointers stay the availability
source of truth until step 5b, so a world-owned member write must appear
to the existing registry readers (``load_relief_templates_for_world``,
``layouts_for_world``) through the pointer row — always pointing at the
world-owned member uid, never at an engine member.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from app.application.jsonValidation.resolve import ResolveContext, resolve_model
from app.application.jsonValidation.worldRow import relief_pick_policy
from app.application.worldData.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.reliefErrors import ReliefValidationError
from app.application.worldData.reliefGeomWarn import warn_template_invalid_geom
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.worldData.reliefWorldImportService import ReliefWorldImportService
from app.application.worldData.structureTemplateLibraryService import (
    StructureTemplateLibraryService,
)
from app.dataModel.locations.structure.building.buildingTemplateOutline import (
    BuildingTemplateOutline,
)
from app.dataModel.locations.structure.building.buildingTemplateRegistryEntry import (
    BuildingTemplateRegistryEntry,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.reliefTemplateRegistryEntry import (
    ReliefTemplateRegistryEntry,
)
from app.dataModel.terrain.relief.worldReliefPickPolicy import (
    ReliefContextPickPolicy,
    WorldReliefPickPolicy,
)
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository
from app.ids import LibraryKind

if TYPE_CHECKING:
    from app.application.worldData.reliefTemplateFsImport import ReliefPackImport
    from app.application.worldData.structureTemplateFsImport import StructurePackImport

logger = logging.getLogger(__name__)

DomainLibrary = (
    ReliefTemplateLibraryService
    | StructureTemplateLibraryService
    | BuildingTemplateLibraryService
)

@dataclass(frozen=True)
class RemappedMember:
    """Instance member + its parsed outline — ``remap_world_refs`` input."""
    member: LibraryPackMemberRow
    outline: Any


class PackDomainAdapter(ABC):
    """Body/pointer contract of one ``library_kind`` for the pack service.

    All methods run inside the caller's transaction — an adapter never owns
    atomicity. ``member_usages`` is the §0.2 used-member policy hook; the
    referenced-set scan lands with step 4c.
    """

    library_kind: ClassVar[LibraryKind]

    @abstractmethod
    async def write_body(
        self,
        raw: dict,
        *,
        local_uid: str,
        template_uid: str,
        pack: LibraryPackRow,
        world: World | None,
        source_file: str | None = None,
    ) -> Any:
        """Validate + persist the body; return the parsed outline.

        Raise ``LibraryPackValidationError`` on invalid body or when the
        body's own identity does not agree with the member identity.
        ``world`` is the owning world for world-owned packs (domain
        restrictions resolve against its registries), else None.
        """

    @abstractmethod
    async def read_body(self, template_uid: str) -> dict | None:
        """Wire dict of the body row, or None when absent."""

    @abstractmethod
    async def delete_body(self, template_uid: str) -> None:
        """Remove the body row; tolerate an already-missing row."""

    async def import_fs_pack(
        self, path: str | Path, *, domain_root: Path | None = None
    ) -> ReliefPackImport | StructurePackImport:
        """Manifest-based FS import → ``(manifest, body rows)`` outcome.

        Domain bodies land via the library service; catalog attach is the
        service's job (same unit of work).
        """
        raise LibraryPackValidationError(
            f"library_kind '{self.library_kind.value}' has no FS domain root"
        )

    async def ensure_pointer(
        self, world: World, member: LibraryPackMemberRow, outline: Any
    ) -> None:
        """Dual-write: refresh the world registry pointer for a member."""

    async def drop_pointer(self, world: World, template_uid: str) -> None:
        """Dual-write: remove the world registry pointer for a member."""

    def member_usages(self, world: World, member: LibraryPackMemberRow) -> list[str]:
        """Diagnostics of world-side uses that block member delete."""
        return []

    # ------------------------------------------------------------------
    # Remap contract (TZ §2) — instantiate_pack / copy_pack, step 4b.
    # ------------------------------------------------------------------

    def remap_body(
        self, body: dict, *, template_uid: str, uid_map: Mapping[str, str]
    ) -> dict:
        """Copied member body for the new owner.

        Rewrites the embedded member uid (model A bodies) and refs to
        source-pack members by ``uid_map``; refs absent from the map —
        other packs, external bodies — stay untouched.
        """
        return dict(body)

    async def body_source_file(self, template_uid: str) -> str | None:
        """Diagnostic ``source_file`` of the body row — carried into copies."""
        return None

    async def remap_world_refs(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> None:
        """Instantiate-time world-side remap (TZ §2).

        Registry pointers land on the *instance* member uids and entries
        still aimed at source members are repointed; the adapter's
        declared world-side ref fields (pick policies, layout-embedded
        structure refs) follow the same map. Runs inside the caller's
        transaction; ``members`` are this kind's freshly written
        instance members.
        """


def _remap_structure_refs(row: dict, uid_map: Mapping[str, str]) -> dict | None:
    """``structure`` uid refs of a plot-layout wire shape → instance uids.

    Declared ref fields of the structure domain (TZ §2):
    ``main_building.structure`` and ``secondary_buildings[].structure``.
    Returns the rewritten dict, or ``None`` when nothing matched — refs
    to other packs stay untouched.
    """
    out = dict(row)
    changed = False
    main = out.get("main_building")
    if isinstance(main, dict) and main.get("structure") in uid_map:
        main = dict(main)
        main["structure"] = uid_map[main["structure"]]
        out["main_building"] = main
        changed = True
    secondary = out.get("secondary_buildings")
    if isinstance(secondary, list):
        items = [
            {**item, "structure": uid_map[item["structure"]]}
            if isinstance(item, dict) and item.get("structure") in uid_map
            else item
            for item in secondary
        ]
        if items != secondary:
            out["secondary_buildings"] = items
            changed = True
    return out if changed else None


def _remap_relief_pick_policy(world: World, uid_map: Mapping[str, str]) -> dict | None:
    """``relief_pick_policy.<context>.default_template_uid`` — the declared
    world-side ref field of the relief domain (TZ §2); other keys stay."""
    raw = world.relief_pick_policy or {}
    if not isinstance(raw, dict):
        return None
    out = dict(raw)
    changed = False
    for name in WorldReliefPickPolicy.model_fields:
        entry = out.get(name)
        if isinstance(entry, dict) and entry.get("default_template_uid") in uid_map:
            entry = dict(entry)
            entry["default_template_uid"] = uid_map[entry["default_template_uid"]]
            out[name] = entry
            changed = True
    return out if changed else None


class _LibraryBodyMixin:
    """Shared body-row CRUD over the domain library service."""

    _library: DomainLibrary

    async def read_body(self, template_uid: str) -> dict | None:
        row = await self._library.find_by_uid(template_uid)
        return None if row is None else dict(row.data)

    async def delete_body(self, template_uid: str) -> None:
        if await self._library.find_by_uid(template_uid) is not None:
            await self._library.delete(template_uid)

    async def body_source_file(self, template_uid: str) -> str | None:
        row = await self._library.find_by_uid(template_uid)
        return None if row is None else row.source_file


class _RegistryPointerMixin:
    """Shared world-registry pointer dual-write for uid-keyed registries.

    Registry columns are written through the world repository as raw
    rows — the same storage path as ``prepare_import``. ``worlds.update``
    would normalize the column against the registry-entry POJO and reject
    non-pointer rows (e.g. embedded plot layouts) that legitimately live
    there.
    """

    registry_field: ClassVar[str]
    _world_repo: IWorldRepository

    async def ensure_pointer(
        self, world: World, member: LibraryPackMemberRow, outline: Any
    ) -> None:
        await self._swap_pointer(
            world,
            template_uid=member.template_uid,
            entry=self._pointer_entry(member, outline),
        )

    async def drop_pointer(self, world: World, template_uid: str) -> None:
        await self._swap_pointer(world, template_uid=template_uid, entry=None)

    async def remap_world_refs(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> None:
        setattr(
            world, self.registry_field,
            self._remapped_registry(world, uid_map, members),
        )
        await self._world_repo.update(world)

    def _remapped_registry(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> list:
        """Registry after instantiate: pointer rows aimed at source or new
        member uids are rebuilt; other rows (foreign pointers, embedded
        plot layouts) pass through untouched — raw-dict scan, not the
        resolved POJO, so non-pointer rows survive."""
        drop = set(uid_map) | {rm.member.template_uid for rm in members}
        entries = [
            row for row in (getattr(world, self.registry_field, None) or [])
            if not (isinstance(row, dict) and row.get("system_template_uid") in drop)
        ]
        entries.extend(
            self._pointer_entry(rm.member, rm.outline).model_dump(mode="json")
            for rm in members
        )
        return entries

    def _pointer_entry(self, member: LibraryPackMemberRow, outline: Any):
        """Registry entry for this member — declared by each domain."""
        raise NotImplementedError

    async def _swap_pointer(
        self, world: World, *, template_uid: str, entry: Any | None
    ) -> None:
        entries = [
            row
            for row in (getattr(world, self.registry_field, None) or [])
            if not (
                isinstance(row, dict)
                and row.get("system_template_uid") == template_uid
            )
        ]
        if entry is not None:
            entries.append(entry.model_dump(mode="json"))
        setattr(world, self.registry_field, entries)
        await self._world_repo.update(world)


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

    async def write_body(
        self,
        raw: dict,
        *,
        local_uid: str,
        template_uid: str,
        pack: LibraryPackRow,
        world: World | None,
        source_file: str | None = None,
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
                warn_template_invalid_geom(outline, source_file=source_file)
        except (ValueError, ReliefValidationError) as exc:
            raise LibraryPackValidationError(str(exc)) from exc
        if outline.system_name != local_uid:
            raise LibraryPackValidationError(
                f"relief body system_name '{outline.system_name}' != "
                f"member local_uid '{local_uid}'"
            )
        await self._library.upsert_outline(
            outline, source_file=source_file, pack_uid=pack.pack_uid
        )
        return outline

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

    def member_usages(
        self, world: World, member: LibraryPackMemberRow
    ) -> list[str]:
        usages: list[str] = []
        policy = relief_pick_policy(world)
        for name in WorldReliefPickPolicy.model_fields:
            entry = getattr(policy, name)
            if (
                isinstance(entry, ReliefContextPickPolicy)
                and entry.default_template_uid == member.template_uid
            ):
                usages.append(f"relief_pick_policy.{name}.default_template_uid")
        return usages

    async def remap_world_refs(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> None:
        setattr(
            world, self.registry_field,
            self._remapped_registry(world, uid_map, members),
        )
        policy = _remap_relief_pick_policy(world, uid_map)
        if policy is not None:
            world.relief_pick_policy = policy
        await self._world_repo.update(world)


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

    async def write_body(
        self,
        raw: dict,
        *,
        local_uid: str,
        template_uid: str,
        pack: LibraryPackRow,
        world: World | None,
        source_file: str | None = None,
    ) -> StructureTemplate:
        if not isinstance(raw, dict):
            raise LibraryPackValidationError(
                f"structure body for '{local_uid}' must be a JSON object"
            )
        payload = dict(raw)
        if payload.get("system_name") is None:
            payload["system_name"] = template_uid
        try:
            outline = resolve_model(StructureTemplate, payload, label=local_uid)
        except ValueError as exc:
            raise LibraryPackValidationError(str(exc)) from exc
        if str(outline.system_name) != template_uid:
            raise LibraryPackValidationError(
                f"structure body system_name '{outline.system_name}' != member "
                f"template_uid '{template_uid}' (model A: body carries the uid)"
            )
        await self._library.upsert_outline(outline, source_file=source_file)
        return outline

    def remap_body(
        self, body: dict, *, template_uid: str, uid_map: Mapping[str, str]
    ) -> dict:
        """Model A: the copied body embeds its new member uid (TZ §2)."""
        out = dict(body)
        out["system_name"] = template_uid
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
        changed = False
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

    async def write_body(
        self,
        raw: dict,
        *,
        local_uid: str,
        template_uid: str,
        pack: LibraryPackRow,
        world: World | None,
        source_file: str | None = None,
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
        await self._library.upsert_outline(
            body, source_file=source_file, pack_uid=pack.pack_uid
        )
        return body

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


def build_pack_domain_adapters(
    *,
    relief_library: ReliefTemplateLibraryService,
    structure_library: StructureTemplateLibraryService,
    building_library: BuildingTemplateLibraryService,
    world_repository: IWorldRepository,
    relief_world_import: ReliefWorldImportService | None = None,
) -> dict[LibraryKind, PackDomainAdapter]:
    """Container seam — one adapter per supported ``library_kind``."""
    return {
        LibraryKind.RELIEF_TEMPLATES: ReliefPackAdapter(
            relief_library, world_repository, relief_world_import
        ),
        LibraryKind.STRUCTURE_TEMPLATES: StructurePackAdapter(
            structure_library, world_repository
        ),
        LibraryKind.BUILDING_TEMPLATES: BuildingPackAdapter(
            building_library, world_repository
        ),
    }
