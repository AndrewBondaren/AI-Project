"""Pack application service — plan library-packs-model.md steps 4a–4b,
TZ §0.2/§1.1/§2/§3.

Single CRUD/ownership boundary over ``library_packs`` +
``library_pack_members`` (+ ``library_pack_dependencies``), plus the §2
remap operations (``instantiate_pack`` engine→world / ``copy_pack``
publish world→engine). Re-instantiate member rewrite and bundle/routes
are later steps (4c/4d).

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

This module is the facade only: shared deps + gates live in
``packScope``, result DTOs in ``packResults``, the member/pack/remap
jobs in ``memberOps``/``packOps``/``remapOps``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.application.worldData.libraryPacks.domainAdapters import PackDomainAdapter
from app.application.worldData.libraryPacks.memberOps import _MemberOps
from app.application.worldData.libraryPacks.packOps import _PackOps
from app.application.worldData.libraryPacks.packResults import (
    MemberDeleteResult,
    PackDeleteResult,
    PackImportResult,
    PackRemapResult,
)
from app.application.worldData.libraryPacks.packScope import _PackScope
from app.application.worldData.libraryPacks.remapOps import _RemapOps
from app.application.worldData.worldService import WorldService
from app.db.database import Database
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.repositories.iLibraryPackDependencyRepository import (
    ILibraryPackDependencyRepository,
)
from app.db.repositories.iLibraryPackMemberRepository import ILibraryPackMemberRepository
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository
from app.ids import LibraryKind


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
        self._remap_ops = _RemapOps(self._scope, self._pack_ops)

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
    # Remap operations (TZ §2) — delegated to the remap job
    # ------------------------------------------------------------------

    async def instantiate_pack(
        self, source_pack_uid: str, *, world_uid: str
    ) -> PackRemapResult:
        """Snapshot-instantiate an engine library into a world (TZ §1.1/§2).

        Full-pack copy: members get deterministic uids from the
        world-owned instance, ``source_pack_uid``/``source_template_uid``
        record provenance, internal body refs and declared world-side
        refs (pick-policy fields, registry pointers, layout-embedded
        structure refs) are repointed at the instance members — pointers
        never aim at a source member. A ``local_uid`` shared with
        another world-owned pack of the world is a collision, not a
        merge. Re-instantiating the same source returns the existing
        instance (``created=False``); member rewrite is step 4c.
        """
        return await self._remap_ops.instantiate(source_pack_uid, world_uid)

    async def copy_pack(
        self, source_pack_uid: str, *, system_name: str | None = None
    ) -> PackRemapResult:
        """Publish a world-owned pack to the engine catalog (TZ §4.1).

        The same §2 remap with ``owner_world_uid=None`` — the source
        world pack, its members and its registry pointers are not
        touched; editing the published library never reaches instances.
        ``system_name`` defaults to ``{source}.published``.
        """
        return await self._remap_ops.copy(
            source_pack_uid, system_name=system_name
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
