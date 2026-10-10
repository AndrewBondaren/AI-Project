"""Member write path of the pack service — TZ §0.2 internal job.

``_MemberOps`` owns member create/update/delete (body + member row +
registry pointer dual-write in one unit of work) plus the usage gates
that block a used-member delete: author pins (``library_pins``) and the
adapter's domain usages.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable

from app.application.worldData.libraryPacks.domainAdapters import PackDomainAdapter
from app.application.worldData.libraryPacks.errors import (
    LibraryPackConflictError,
    LibraryPackInUseError,
    LibraryPackNotFoundError,
    LibraryPackValidationError,
)
from app.application.worldData.libraryPacks.packResults import MemberDeleteResult
from app.application.worldData.libraryPacks.packScope import _PackScope, _coerce_kind
from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.ids import LibraryKind, library_uid

logger = logging.getLogger(__name__)


def _validate_local_uid(local_uid: str) -> str:
    local_uid = (local_uid or "").strip()
    if not local_uid:
        raise LibraryPackValidationError("local_uid is required")
    if "|" in local_uid:
        raise LibraryPackValidationError(
            f"local_uid must not contain '|': {local_uid!r}"
        )
    return local_uid


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
