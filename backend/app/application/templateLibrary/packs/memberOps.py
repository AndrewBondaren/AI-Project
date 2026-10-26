"""Member reads and explicit usage-gated deletion — TZ §0.2.

Create/copy/replace are handled by the common LibraryWriteService.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from app.application.templateLibrary.packs.errors import (
    LibraryPackInUseError,
    LibraryPackNotFoundError,
    LibraryPackValidationError,
)
from app.application.templateLibrary.packs.packResults import MemberDeleteResult
from app.application.templateLibrary.packs.packScope import _PackScope
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, UID_PART_SEPARATOR

logger = logging.getLogger(__name__)


def _validate_local_uid(local_uid: str) -> str:
    local_uid = (local_uid or "").strip()
    if not local_uid:
        raise LibraryPackValidationError("local_uid is required")
    if UID_PART_SEPARATOR in local_uid:
        raise LibraryPackValidationError(
            f"local_uid must not contain {UID_PART_SEPARATOR!r}: {local_uid!r}"
        )
    return local_uid


class _MemberOps:
    """Member read/delete job of the pack service."""

    def __init__(self, scope: _PackScope) -> None:
        self._scope = scope

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
        from app.application.templateLibrary.packs.referenceResolver import member_usages
        usages = await member_usages(scope, member, world)
        if usages and not allow_used:
            raise LibraryPackInUseError(
                f"member '{member.local_uid}' is in use: {usages}",
                usages=tuple(usages),
            )

        async def _write() -> None:
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

    async def teardown(
        self, members: Iterable[LibraryPackMemberRow]
    ) -> list[str]:
        """Drop bodies of all members (pack delete path).

        Members whose kind has no wired adapter get an orphan diagnostic;
        their member rows still cascade with the pack delete. Registry
        pointers no longer exist (B6) — nothing world-side to unwind.
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
