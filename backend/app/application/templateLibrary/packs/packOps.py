"""Pack-level read/write path of the pack service — TZ §0.2/§3/§4
internal job: empty-pack CRUD, metadata and dependency declaration."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import replace

from app.application.worldData.libraryPacks.errors import (
    LibraryPackInUseError,
    LibraryPackNotFoundError,
    LibraryPackValidationError,
)
from app.application.worldData.libraryPacks.memberOps import _MemberOps
from app.application.worldData.libraryPacks.packResults import (
    PackDeleteResult,
)
from app.application.worldData.libraryPacks.packIdentity import PACK_NAME_SEPARATOR
from app.application.worldData.libraryPacks.packScope import _PackScope
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackDependency import LibraryPackDependencyRow
from app.ids import UID_PART_SEPARATOR

logger = logging.getLogger(__name__)


def _validate_dependencies(pack_uid: str, dependencies: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for dep in dependencies:
        dep = (dep or "").strip()
        if not dep:
            raise LibraryPackValidationError("dependency uid must be non-empty")
        if UID_PART_SEPARATOR in dep:
            raise LibraryPackValidationError(
                f"dependency uid must not contain {UID_PART_SEPARATOR!r}: {dep!r}"
            )
        if dep == pack_uid:
            raise LibraryPackValidationError("a pack cannot depend on itself")
        if dep not in seen:
            seen.append(dep)
    return seen


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
        version: str = LibraryPackRow.version,
        owner_world_uid: str | None = None,
        dependencies: Iterable[str] = (),
    ) -> LibraryPackRow:
        scope = self._scope
        if owner_world_uid is not None and (
            await scope.worlds.find_by_id(owner_world_uid) is None
        ):
            raise LibraryPackValidationError(
                f"owner world '{owner_world_uid}' does not exist"
            )
        system_name, pack_uid = await scope.new_pack_identity(system_name)
        dep_uids = _validate_dependencies(pack_uid, dependencies)
        row = LibraryPackRow(
            pack_uid=pack_uid,
            system_name=system_name,
            pack_name=pack_name or system_name.rsplit(PACK_NAME_SEPARATOR, 1)[-1],
            display_name=display_name or pack_name or system_name,
            version=version,
            owner_world_uid=owner_world_uid,
        )

        async def _write() -> None:
            await scope.insert_pack_row(row)
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

        async def _write() -> None:
            diagnostics.extend(await self._members.teardown(members))
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
