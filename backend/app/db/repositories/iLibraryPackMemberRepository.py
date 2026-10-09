"""Interface for the ``library_pack_members`` catalog — tz_template_library_packs §3.

Persistence primitives only (plan B-2). ``template_uid`` is the single
identity of a member: one row = one owner; a link to another pack's
template cannot be written as own membership. No replace/upsert path —
identity change is a new row, not a mutation (TZ §2). "Held by use" and
"source deleted" are computed from provenance resolution, not stored.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.db.models.libraryPackMember import LibraryPackMemberRow


class ILibraryPackMemberRepository(ABC):

    @abstractmethod
    async def insert(self, member: LibraryPackMemberRow) -> None:
        """Strict insert; PK/UNIQUE/FK violations raise."""
        ...

    @abstractmethod
    async def insert_missing(self, members: Sequence[LibraryPackMemberRow]) -> int:
        """Atomic fill-missing (TZ §6): ``ON CONFLICT(template_uid) DO NOTHING``.

        Existing membership — including another owner's row for the same
        ``template_uid`` — is never replaced (membership never changes
        owner). A ``UNIQUE(pack_uid, library_kind, local_uid)`` collision
        or FK violation raises and rolls the batch back.
        Owns a transaction only when the caller is not inside one.
        Returns the number of inserted rows.
        """
        ...

    @abstractmethod
    async def existing_uids(self, template_uids: Sequence[str]) -> set[str]:
        """Presence primitive: completeness is checked by canonical UID
        and membership, not by a non-empty table (TZ §6)."""
        ...

    @abstractmethod
    async def get_by_uid(self, template_uid: str) -> LibraryPackMemberRow | None:
        """Membership lookup: UID → single owner (TZ §5 resolve path)."""
        ...

    @abstractmethod
    async def find_by_local_uid(
        self,
        pack_uid: str,
        library_kind: str,
        local_uid: str,
    ) -> LibraryPackMemberRow | None: ...

    @abstractmethod
    async def list_by_pack(self, pack_uid: str) -> list[LibraryPackMemberRow]: ...

    @abstractmethod
    async def list_by_packs(self, pack_uids: Sequence[str]) -> list[LibraryPackMemberRow]:
        """Members of an explicit pack set (defaults + world packs —
        the effective-catalog primitive)."""
        ...

    @abstractmethod
    async def list_for_world(self, owner_world_uid: str) -> list[LibraryPackMemberRow]:
        """Members of packs owned by one world (JOIN over packs)."""
        ...

    @abstractmethod
    async def delete(self, template_uid: str) -> None: ...

    @abstractmethod
    async def delete_by_pack(self, pack_uid: str) -> int:
        """Remove all members of a pack; returns the number removed."""
        ...
