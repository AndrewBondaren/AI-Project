"""Pack application service — plan library-packs-model.md step 4a, TZ §0.2/§1.1/§3.

Single CRUD/ownership boundary over ``library_packs`` +
``library_pack_members`` (+ ``library_pack_dependencies``). Remap
operations (``instantiate_pack``/``copy_pack``), re-instantiate and
bundle/routes are later steps (4b/4c/4d).

Ownership semantics (TZ §1.1 — availability = ownership or default):

- Engine user libraries (``owner_world_uid IS NULL``) are fully editable;
  deleting one is always safe for worlds — worlds hold copied instances.
- Declared default packs are read-only; the sole mutation is the additive
  canonical attach (trusted FS import path — steps 6–7 own the mechanics).
- World-owned packs are editable inside their world only.

Dual-write (transitional, until step 5b): member writes into a world-owned
pack also write the world registry pointer — at the *world-owned* member
uid, never an engine member — so existing registry readers resolve the
member. Member delete drops the pointer in the same transaction.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.application.worldData.libraryPacks.defaults import is_default_pack_uid
from app.application.worldData.libraryPacks.domainAdapters import PackDomainAdapter
from app.application.worldData.libraryPacks.errors import (
    LibraryPackConflictError,
    LibraryPackInUseError,
    LibraryPackNotFoundError,
    LibraryPackOwnershipError,
    LibraryPackReadOnlyError,
    LibraryPackValidationError,
)
from app.application.worldData.libraryPacks.packCatalog import (
    PackCatalogRepos,
    attach_pack_catalog,
)
from app.application.worldData.worldService import WorldService
from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
from app.db.database import Database
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackDependency import LibraryPackDependencyRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.reliefTemplate import ReliefTemplateRow
from app.db.models.structureTemplate import StructureTemplateRow
from app.db.models.world import World
from app.db.repositories.iLibraryPackDependencyRepository import (
    ILibraryPackDependencyRepository,
)
from app.db.repositories.iLibraryPackMemberRepository import ILibraryPackMemberRepository
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository
from app.ids import LibraryKind, library_uid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PackDeleteResult:
    pack_uid: str
    members_removed: int
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemberDeleteResult:
    template_uid: str
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class PackImportResult:
    pack: LibraryPackRow
    bodies: tuple[ReliefTemplateRow | StructureTemplateRow, ...]
    missing_dependencies: tuple[str, ...] = ()


def _coerce_kind(library_kind: str | LibraryKind) -> LibraryKind:
    try:
        kind = LibraryKind(library_kind)
    except ValueError as exc:
        raise LibraryPackValidationError(
            f"unknown library_kind '{library_kind}'"
        ) from exc
    if kind is LibraryKind.LIBRARY_PACKS:
        raise LibraryPackValidationError("library_packs is not a member domain")
    return kind


def _validate_local_uid(local_uid: str) -> str:
    local_uid = (local_uid or "").strip()
    if not local_uid:
        raise LibraryPackValidationError("local_uid is required")
    if "|" in local_uid:
        raise LibraryPackValidationError(
            f"local_uid must not contain '|': {local_uid!r}"
        )
    return local_uid


def _validate_dependencies(pack_uid: str, dependencies: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for dep in dependencies:
        dep = (dep or "").strip()
        if not dep:
            raise LibraryPackValidationError("dependency uid must be non-empty")
        if "|" in dep:
            raise LibraryPackValidationError(
                f"dependency uid must not contain '|': {dep!r}"
            )
        if dep == pack_uid:
            raise LibraryPackValidationError("a pack cannot depend on itself")
        if dep not in seen:
            seen.append(dep)
    return seen


def _pin_usages(world: World, member: LibraryPackMemberRow) -> list[str]:
    """Author pins ``(library_kind, local_uid)`` naming this member (TZ §1.1)."""
    for raw_pin in world.library_pins or []:
        pin = LibraryPinEntry.model_validate(raw_pin)
        if (
            pin.library_kind == member.library_kind
            and pin.local_uid == member.local_uid
        ):
            return [f"pinned by world '{world.world_uid}' (library_pins)"]
    return []


class _PackScope:
    """Shared deps + gates for pack- and member-level operations."""

    def __init__(
        self,
        *,
        db: Database | None,
        packs: ILibraryPackRepository,
        members: ILibraryPackMemberRepository,
        deps: ILibraryPackDependencyRepository,
        world_service: WorldService,
        adapters: dict[LibraryKind, PackDomainAdapter],
    ) -> None:
        self.db = db
        self.packs = packs
        self.members = members
        self.deps = deps
        self.catalog = PackCatalogRepos(packs=packs, members=members, deps=deps)
        self.worlds = world_service
        self.adapters = dict(adapters)

    async def atomic(self, op: Callable[[], Awaitable[Any]]) -> Any:
        """One unit of work; reuses an outer transaction when present."""
        if self.db is not None:
            async with self.db.transaction_if_needed():
                return await op()
        return await op()

    def require_writable(self, pack: LibraryPackRow) -> None:
        """TZ §1.1 gate: declared defaults are read-only; world-owned packs
        mutate only inside their owning world (the row IS the owner)."""
        if is_default_pack_uid(pack.pack_uid):
            raise LibraryPackReadOnlyError(
                f"pack '{pack.system_name}' is a declared default — read-only; "
                "the only mutation is additive canonical attach (TZ §6)"
            )

    def require_owner_scope(
        self, pack: LibraryPackRow, world_uid: str | None
    ) -> None:
        """A world-owned pack mutates only under its owner's context —
        the caller cannot reach another world's pack (TZ §1.1)."""
        if (
            pack.owner_world_uid is not None
            and world_uid != pack.owner_world_uid
        ):
            raise LibraryPackOwnershipError(
                f"pack '{pack.system_name}' is owned by world "
                f"'{pack.owner_world_uid}' — caller scope {world_uid!r} rejected"
            )

    async def world_for(self, pack: LibraryPackRow) -> World | None:
        if pack.owner_world_uid is None:
            return None
        return await self.worlds.get_by_id(pack.owner_world_uid)

    def adapter_for(self, kind: LibraryKind) -> PackDomainAdapter:
        adapter = self.adapters.get(kind)
        if adapter is None:
            raise LibraryPackValidationError(
                f"library_kind '{kind.value}' has no domain adapter wired"
            )
        return adapter

    async def missing_uids(self, pack_uid: str) -> set[str]:
        """Declared dependencies not present in the catalog (§3 diagnose)."""
        required = await self.deps.required_uids(pack_uid)
        if not required:
            return set()
        return required - await self.packs.existing_uids(sorted(required))

    async def diagnose_missing(self, pack: LibraryPackRow) -> set[str]:
        """Log + return declared dependencies absent from the catalog."""
        missing = await self.missing_uids(pack.pack_uid)
        if missing:
            logger.warning(
                "packs | pack=%s has missing dependencies: %s",
                pack.system_name, sorted(missing),
            )
        return missing


class _MemberOps:
    """Member write path of TZ §0.2 — internal job of the pack service."""

    def __init__(self, scope: _PackScope) -> None:
        self._scope = scope

    async def create(
        self,
        pack_uid: str,
        *,
        library_kind: str | LibraryKind,
        local_uid: str,
        body: dict,
        source_file: str | None = None,
        world_uid: str | None = None,
    ) -> LibraryPackMemberRow:
        scope = self._scope
        pack = await scope.packs.get_by_uid(pack_uid)
        if pack is None:
            raise LibraryPackNotFoundError(f"pack '{pack_uid}' not found")
        scope.require_writable(pack)
        scope.require_owner_scope(pack, world_uid)
        kind = _coerce_kind(library_kind)
        adapter = scope.adapter_for(kind)
        local_uid = _validate_local_uid(local_uid)
        template_uid = library_uid(kind, local_uid, pack_uid=pack_uid)
        world = await scope.world_for(pack)
        await scope.diagnose_missing(pack)

        member = LibraryPackMemberRow(
            template_uid=template_uid,
            pack_uid=pack_uid,
            library_kind=kind.value,
            local_uid=local_uid,
        )

        async def _write() -> None:
            if (
                await scope.members.find_by_local_uid(pack_uid, kind.value, local_uid)
                is not None
            ):
                raise LibraryPackConflictError(
                    f"local_uid '{local_uid}' already exists in pack "
                    f"'{pack.system_name}' ({kind.value})"
                )
            outline = await adapter.write_body(
                body,
                local_uid=local_uid,
                template_uid=template_uid,
                pack=pack,
                world=world,
                source_file=source_file,
            )
            try:
                await scope.members.insert(member)
            except sqlite3.IntegrityError as exc:
                raise LibraryPackConflictError(
                    f"member '{local_uid}' conflicts with an existing row: {exc}"
                ) from exc
            if world is not None:
                # Dual-write: the pointer targets THIS world-owned member uid.
                await adapter.ensure_pointer(world, member, outline)

        await scope.atomic(_write)
        return member

    async def update_body(
        self, template_uid: str, body: dict, *, world_uid: str | None = None
    ) -> LibraryPackMemberRow:
        """Replace a member's body — member identity stays immutable."""
        scope = self._scope
        member = await self.require_member(template_uid)
        pack = await self._require_pack(member.pack_uid)
        scope.require_writable(pack)
        scope.require_owner_scope(pack, world_uid)
        adapter = scope.adapter_for(LibraryKind(member.library_kind))
        world = await scope.world_for(pack)

        async def _write() -> None:
            outline = await adapter.write_body(
                body,
                local_uid=member.local_uid,
                template_uid=member.template_uid,
                pack=pack,
                world=world,
            )
            if world is not None:
                await adapter.drop_pointer(world, template_uid)
                await adapter.ensure_pointer(world, member, outline)

        await scope.atomic(_write)
        return member

    async def delete(
        self,
        template_uid: str,
        *,
        allow_used: bool = False,
        world_uid: str | None = None,
    ) -> MemberDeleteResult:
        """Explicit §0.2 delete policy: refuse while used (pin/reader).

        ``allow_used`` overrides — the usages are still reported as
        diagnostics so the caller can repair the dangling references.
        """
        scope = self._scope
        member = await self.require_member(template_uid)
        pack = await self._require_pack(member.pack_uid)
        scope.require_writable(pack)
        scope.require_owner_scope(pack, world_uid)
        adapter = scope.adapter_for(LibraryKind(member.library_kind))
        world = await scope.world_for(pack)
        usages = self._usages(world, member, adapter)
        if usages and not allow_used:
            raise LibraryPackInUseError(
                f"member '{member.local_uid}' is in use: {usages}",
                usages=tuple(usages),
            )

        async def _write() -> None:
            if world is not None:
                await adapter.drop_pointer(world, template_uid)
            await adapter.delete_body(template_uid)
            await scope.members.delete(template_uid)

        await scope.atomic(_write)
        for usage in usages:
            logger.warning(
                "packs | member=%s deleted while still used: %s",
                template_uid, usage,
            )
        return MemberDeleteResult(
            template_uid=template_uid, diagnostics=tuple(usages)
        )

    async def read_body(self, template_uid: str) -> dict | None:
        member = await self.require_member(template_uid)
        return await self._scope.adapter_for(
            LibraryKind(member.library_kind)
        ).read_body(template_uid)

    @staticmethod
    def _usages(
        world: World | None,
        member: LibraryPackMemberRow,
        adapter: PackDomainAdapter,
    ) -> list[str]:
        if world is None:
            return []  # engine members are never inside a world's catalog
        return _pin_usages(world, member) + adapter.member_usages(world, member)

    async def teardown(
        self,
        members: Iterable[LibraryPackMemberRow],
        world: World | None,
    ) -> list[str]:
        """Drop pointers + bodies of all members (pack delete path).

        Members whose kind has no wired adapter get an orphan diagnostic;
        their member rows still cascade with the pack delete.
        """
        diagnostics: list[str] = []
        for member in members:
            adapter = self._scope.adapters.get(LibraryKind(member.library_kind))
            if adapter is None:
                diagnostics.append(
                    f"no adapter for kind '{member.library_kind}' — "
                    f"body '{member.template_uid}' left orphaned"
                )
                continue
            if world is not None:
                await adapter.drop_pointer(world, member.template_uid)
            await adapter.delete_body(member.template_uid)
        return diagnostics

    async def require_member(self, template_uid: str) -> LibraryPackMemberRow:
        member = await self._scope.members.get_by_uid(template_uid)
        if member is None:
            raise LibraryPackNotFoundError(f"member '{template_uid}' not found")
        return member

    async def _require_pack(self, pack_uid: str) -> LibraryPackRow:
        pack = await self._scope.packs.get_by_uid(pack_uid)
        if pack is None:
            raise LibraryPackNotFoundError(f"pack '{pack_uid}' not found")
        return pack


class _PackOps:
    """Pack-level read/write path of TZ §0.2/§3 — internal job."""

    def __init__(self, scope: _PackScope, members: _MemberOps) -> None:
        self._scope = scope
        self._members = members  # member teardown on pack delete

    async def create(
        self,
        *,
        system_name: str,
        pack_name: str | None = None,
        display_name: str | None = None,
        version: str = "1.0",
        owner_world_uid: str | None = None,
        dependencies: Iterable[str] = (),
    ) -> LibraryPackRow:
        scope = self._scope
        system_name = (system_name or "").strip()
        if not system_name:
            raise LibraryPackValidationError("system_name is required")
        try:
            pack_uid = library_uid(LibraryKind.LIBRARY_PACKS, system_name)
        except ValueError as exc:
            raise LibraryPackValidationError(str(exc)) from exc
        if is_default_pack_uid(pack_uid):
            raise LibraryPackReadOnlyError(
                f"system_name '{system_name}' resolves to a declared default "
                "pack — defaults arrive only via the trusted source (TZ §6)"
            )
        if owner_world_uid is not None and (
            await scope.worlds.find_by_id(owner_world_uid) is None
        ):
            raise LibraryPackValidationError(
                f"owner world '{owner_world_uid}' does not exist"
            )
        dep_uids = _validate_dependencies(pack_uid, dependencies)
        if (
            await scope.packs.get_by_uid(pack_uid) is not None
            or await scope.packs.get_by_system_name(system_name) is not None
        ):
            raise LibraryPackConflictError(
                f"pack system_name '{system_name}' already exists"
            )
        row = LibraryPackRow(
            pack_uid=pack_uid,
            system_name=system_name,
            pack_name=pack_name or system_name.rsplit(".", 1)[-1],
            display_name=display_name or pack_name or system_name,
            version=version,
            owner_world_uid=owner_world_uid,
        )

        async def _write() -> None:
            try:
                await scope.packs.insert(row)
            except sqlite3.IntegrityError as exc:
                raise LibraryPackConflictError(
                    f"pack '{system_name}' conflicts with an existing row: {exc}"
                ) from exc
            if dep_uids:
                await scope.deps.insert_missing(
                    [LibraryPackDependencyRow(row.pack_uid, dep) for dep in dep_uids]
                )

        await scope.atomic(_write)
        await scope.diagnose_missing(row)
        return row

    async def get(self, pack_uid: str) -> LibraryPackRow:
        pack = await self._scope.packs.get_by_uid(pack_uid)
        if pack is None:
            raise LibraryPackNotFoundError(f"pack '{pack_uid}' not found")
        return pack

    async def find(self, pack_uid: str) -> LibraryPackRow | None:
        return await self._scope.packs.get_by_uid(pack_uid)

    async def list_all(self) -> list[LibraryPackRow]:
        return await self._scope.packs.list_all()

    async def list_engine(self) -> list[LibraryPackRow]:
        return await self._scope.packs.list_engine()

    async def list_world_owned(self, owner_world_uid: str) -> list[LibraryPackRow]:
        return await self._scope.packs.list_world_owned(owner_world_uid)

    async def update_metadata(
        self,
        pack_uid: str,
        *,
        pack_name: str | None = None,
        display_name: str | None = None,
        version: str | None = None,
        world_uid: str | None = None,
    ) -> LibraryPackRow:
        """Mutable metadata only — identity/provenance/owner never change."""
        pack = await self.get(pack_uid)
        self._scope.require_writable(pack)
        self._scope.require_owner_scope(pack, world_uid)
        updated = replace(
            pack,
            pack_name=pack_name if pack_name is not None else pack.pack_name,
            display_name=display_name if display_name is not None else pack.display_name,
            version=version if version is not None else pack.version,
        )
        if updated == pack:
            return pack
        await self._scope.packs.update_metadata(updated)
        return updated

    async def delete(
        self,
        pack_uid: str,
        *,
        force: bool = False,
        world_uid: str | None = None,
    ) -> PackDeleteResult:
        scope = self._scope
        pack = await self.get(pack_uid)
        scope.require_writable(pack)
        scope.require_owner_scope(pack, world_uid)
        dependents = await scope.deps.list_dependents(pack_uid)
        diagnostics: list[str] = []
        if dependents:
            names = sorted(d.pack_uid for d in dependents)
            msg = (
                f"pack '{pack.system_name}' is declared as a dependency of "
                f"{names}"
            )
            if not force:
                raise LibraryPackInUseError(msg, usages=tuple(names))
            diagnostics.append(f"{msg} — left dangling after delete")
        members = await scope.members.list_by_pack(pack_uid)
        world = await scope.world_for(pack)

        async def _write() -> None:
            diagnostics.extend(await self._members.teardown(members, world))
            await scope.packs.delete(pack_uid)  # members/deps rows cascade

        await scope.atomic(_write)
        logger.info(
            "packs | delete pack=%s system_name=%s members=%d",
            pack_uid, pack.system_name, len(members),
        )
        return PackDeleteResult(
            pack_uid=pack_uid,
            members_removed=len(members),
            diagnostics=tuple(diagnostics),
        )

    async def set_dependencies(
        self,
        pack_uid: str,
        required_pack_uids: Iterable[str],
        *,
        world_uid: str | None = None,
    ) -> tuple[str, ...]:
        """Replace the dependency declaration; returns the missing uids."""
        scope = self._scope
        pack = await self.get(pack_uid)
        scope.require_writable(pack)
        scope.require_owner_scope(pack, world_uid)
        dep_uids = _validate_dependencies(pack_uid, required_pack_uids)

        async def _write() -> None:
            await scope.deps.delete_for_pack(pack_uid)
            if dep_uids:
                await scope.deps.insert_missing(
                    [LibraryPackDependencyRow(pack_uid, dep) for dep in dep_uids]
                )

        await scope.atomic(_write)
        missing = await scope.diagnose_missing(pack)
        return tuple(sorted(missing))

    async def missing_dependencies(self, pack_uid: str) -> set[str]:
        return await self._scope.missing_uids(pack_uid)

    async def import_fs_pack(
        self,
        library_kind: str | LibraryKind,
        path: str | Path,
        *,
        domain_root: Path | None = None,
    ) -> PackImportResult:
        """Bodies + catalog attach, one unit of work (trusted-source write)."""
        scope = self._scope
        kind = _coerce_kind(library_kind)
        adapter = scope.adapter_for(kind)

        async def _write():
            outcome = await adapter.import_fs_pack(path, domain_root=domain_root)
            await attach_pack_catalog(outcome.manifest, scope.catalog)
            return outcome

        outcome = await scope.atomic(_write)
        pack = await scope.packs.get_by_uid(outcome.manifest.pack_uid)
        if pack is None:
            raise LibraryPackNotFoundError(
                f"imported pack '{outcome.manifest.pack_uid}' missing after attach"
            )
        missing = await scope.diagnose_missing(pack)
        return PackImportResult(
            pack=pack,
            bodies=tuple(outcome.rows),
            missing_dependencies=tuple(sorted(missing)),
        )


class LibraryPackService:
    """Pack + member CRUD with ownership enforcement — step 4a facade."""

    def __init__(
        self,
        *,
        db: Database | None,
        packs: ILibraryPackRepository,
        members: ILibraryPackMemberRepository,
        deps: ILibraryPackDependencyRepository,
        world_service: WorldService,
        adapters: dict[LibraryKind, PackDomainAdapter],
    ) -> None:
        self._scope = _PackScope(
            db=db,
            packs=packs,
            members=members,
            deps=deps,
            world_service=world_service,
            adapters=adapters,
        )
        self._member_ops = _MemberOps(self._scope)
        self._pack_ops = _PackOps(self._scope, self._member_ops)

    # ------------------------------------------------------------------
    # Pack CRUD — delegated to the pack write job
    # ------------------------------------------------------------------

    async def create_pack(
        self,
        *,
        system_name: str,
        pack_name: str | None = None,
        display_name: str | None = None,
        version: str = "1.0",
        owner_world_uid: str | None = None,
        dependencies: Iterable[str] = (),
    ) -> LibraryPackRow:
        """Create an engine (``owner_world_uid=None``) or world-owned pack.

        Default-pack identity is reserved: a caller can never mint a pack
        whose ``system_name`` resolves to a declared default uid (TZ §3).
        Missing dependencies are diagnosed, not blocked (§3: no FK).
        """
        return await self._pack_ops.create(
            system_name=system_name,
            pack_name=pack_name,
            display_name=display_name,
            version=version,
            owner_world_uid=owner_world_uid,
            dependencies=dependencies,
        )

    async def get_pack(self, pack_uid: str) -> LibraryPackRow:
        return await self._pack_ops.get(pack_uid)

    async def find_pack(self, pack_uid: str) -> LibraryPackRow | None:
        return await self._pack_ops.find(pack_uid)

    async def list_packs(self) -> list[LibraryPackRow]:
        """Administrative listing — never the availability catalog."""
        return await self._pack_ops.list_all()

    async def list_engine_packs(self) -> list[LibraryPackRow]:
        return await self._pack_ops.list_engine()

    async def list_world_packs(self, owner_world_uid: str) -> list[LibraryPackRow]:
        return await self._pack_ops.list_world_owned(owner_world_uid)

    async def update_pack_metadata(
        self,
        pack_uid: str,
        *,
        pack_name: str | None = None,
        display_name: str | None = None,
        version: str | None = None,
        world_uid: str | None = None,
    ) -> LibraryPackRow:
        """Mutable metadata only — identity/provenance/owner never change."""
        return await self._pack_ops.update_metadata(
            pack_uid,
            pack_name=pack_name,
            display_name=display_name,
            version=version,
            world_uid=world_uid,
        )

    async def delete_pack(
        self,
        pack_uid: str,
        *,
        force: bool = False,
        world_uid: str | None = None,
    ) -> PackDeleteResult:
        """Delete pack + members + bodies.

        Engine-pack delete is always safe for worlds (they hold instance
        copies). Declared dependents block the delete unless ``force`` —
        then they keep a dangling ``required_pack_uid``, diagnosed here.
        World-owned packs additionally drop their registry pointers.
        """
        return await self._pack_ops.delete(
            pack_uid, force=force, world_uid=world_uid
        )

    async def set_dependencies(
        self,
        pack_uid: str,
        required_pack_uids: Iterable[str],
        *,
        world_uid: str | None = None,
    ) -> tuple[str, ...]:
        """Replace the dependency declaration; returns the missing uids."""
        return await self._pack_ops.set_dependencies(
            pack_uid, required_pack_uids, world_uid=world_uid
        )

    async def missing_dependencies(self, pack_uid: str) -> set[str]:
        return await self._pack_ops.missing_dependencies(pack_uid)

    async def import_fs_pack(
        self,
        library_kind: str | LibraryKind,
        path: str | Path,
        *,
        domain_root: Path | None = None,
    ) -> PackImportResult:
        """Manifest-based FS import → engine library (TZ §4).

        Trusted-source write: a manifest whose identity is a declared
        default performs the additive canonical attach (insert-missing);
        a user pack never gains default status or world availability by
        landing in the catalog.
        """
        return await self._pack_ops.import_fs_pack(
            library_kind, path, domain_root=domain_root
        )

    # ------------------------------------------------------------------
    # Member CRUD (TZ §0.2) — delegated to the member write job
    # ------------------------------------------------------------------

    async def create_member(
        self,
        pack_uid: str,
        *,
        library_kind: str | LibraryKind,
        local_uid: str,
        body: dict,
        source_file: str | None = None,
        world_uid: str | None = None,
    ) -> LibraryPackMemberRow:
        """Validate + write body and member atomically (no partial apply)."""
        return await self._member_ops.create(
            pack_uid,
            library_kind=library_kind,
            local_uid=local_uid,
            body=body,
            source_file=source_file,
            world_uid=world_uid,
        )

    async def get_member(self, template_uid: str) -> LibraryPackMemberRow:
        return await self._member_ops.require_member(template_uid)

    async def list_members(self, pack_uid: str) -> list[LibraryPackMemberRow]:
        await self._pack_ops.get(pack_uid)
        return await self._scope.members.list_by_pack(pack_uid)

    async def read_member_body(self, template_uid: str) -> dict | None:
        return await self._member_ops.read_body(template_uid)

    async def update_member_body(
        self, template_uid: str, body: dict, *, world_uid: str | None = None
    ) -> LibraryPackMemberRow:
        """Replace a member's body — identity change is delete + create."""
        return await self._member_ops.update_body(
            template_uid, body, world_uid=world_uid
        )

    async def delete_member(
        self,
        template_uid: str,
        *,
        allow_used: bool = False,
        world_uid: str | None = None,
    ) -> MemberDeleteResult:
        """Refuses while the member is in use; ``allow_used`` overrides
        with diagnostics (TZ §0.2 explicit delete policy)."""
        return await self._member_ops.delete(
            template_uid, allow_used=allow_used, world_uid=world_uid
        )
