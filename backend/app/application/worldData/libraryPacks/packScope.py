"""Shared scope + gates of the pack service — internal job helpers.

``_PackScope`` bundles the repositories, the domain-adapter map, the
atomic-unit wrapper and the cross-cutting gates (TZ §1.1/§3/§6) used by
``_MemberOps``, ``_PackOps`` and ``_RemapOps``. ``_coerce_kind`` is the
shared member-domain gate.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Awaitable, Callable
from typing import Any

from app.application.worldData.libraryPacks.defaults import is_default_pack_uid
from app.application.worldData.libraryPacks.domainAdapters import PackDomainAdapter
from app.application.worldData.libraryPacks.errors import (
    LibraryPackConflictError,
    LibraryPackOwnershipError,
    LibraryPackReadOnlyError,
    LibraryPackValidationError,
)
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.application.worldData.worldService import WorldService
from app.db.database import Database
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.world import World
from app.db.repositories.iLibraryPackDependencyRepository import (
    ILibraryPackDependencyRepository,
)
from app.db.repositories.iLibraryPackMemberRepository import ILibraryPackMemberRepository
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository
from app.ids import LibraryKind, library_uid

logger = logging.getLogger(__name__)


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

    async def new_pack_identity(self, system_name: str) -> tuple[str, str]:
        """Strip + gate ``system_name`` → ``(system_name, fresh pack_uid)``.

        One identity gate for every pack write (TZ §2/§6): name is
        required, uid comes only from the central formula,
        declared-default identity is reserved, the name is unique.
        """
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
        if (
            await self.packs.get_by_uid(pack_uid) is not None
            or await self.packs.get_by_system_name(system_name) is not None
        ):
            raise LibraryPackConflictError(
                f"pack system_name '{system_name}' already exists"
            )
        return system_name, pack_uid

    async def insert_pack_row(self, row: LibraryPackRow) -> None:
        """Shared insert + conflict mapping; never opens a transaction."""
        try:
            await self.packs.insert(row)
        except sqlite3.IntegrityError as exc:
            raise LibraryPackConflictError(
                f"pack '{row.system_name}' conflicts with an existing row: {exc}"
            ) from exc

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
