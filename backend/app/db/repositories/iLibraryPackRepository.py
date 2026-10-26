"""Interface for the ``library_packs`` catalog — tz_template_library_packs §3.

Persistence primitives only (plan B-2): ownership rules, default-pack
status and CRUD checks live in the pack application service (step 4a).
No replace/upsert path: ``pack_uid`` is assigned once and never rewritten.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.db.models.libraryPack import LibraryPackRow


class ILibraryPackRepository(ABC):

    @abstractmethod
    async def insert(self, pack: LibraryPackRow) -> None:
        """Strict insert of a new pack; PK/UNIQUE violations raise."""
        ...

    @abstractmethod
    async def insert_missing(self, packs: Sequence[LibraryPackRow]) -> int:
        """Atomic fill-missing (TZ §6): ``ON CONFLICT(pack_uid) DO NOTHING``.

        Existing rows are never replaced; a ``system_name`` collision or any
        other constraint violation raises and rolls the batch back.
        Owns a transaction only when the caller is not inside one.
        Returns the number of inserted rows.
        """
        ...

    @abstractmethod
    async def existing_uids(self, pack_uids: Sequence[str]) -> set[str]:
        """Presence primitive for completeness checks (TZ §6)."""
        ...

    @abstractmethod
    async def get_by_uid(self, pack_uid: str) -> LibraryPackRow | None: ...

    @abstractmethod
    async def get_by_system_name(self, system_name: str) -> LibraryPackRow | None:
        """Lookup by the globally UNIQUE ``system_name`` key."""
        ...

    @abstractmethod
    async def list_all(self) -> list[LibraryPackRow]:
        """Administrative listing — never the generation catalog."""
        ...

    @abstractmethod
    async def list_engine(self) -> list[LibraryPackRow]:
        """Engine libraries (``owner_world_uid IS NULL``)."""
        ...

    @abstractmethod
    async def list_world_owned(self, owner_world_uid: str) -> list[LibraryPackRow]:
        """Libraries owned by one world."""
        ...

    @abstractmethod
    async def find_instance(
        self,
        owner_world_uid: str,
        source_pack_uid: str,
    ) -> LibraryPackRow | None:
        """World instance of a source pack — provenance lookup for
        idempotent re-instantiate (TZ §2)."""
        ...

    @abstractmethod
    async def update_metadata(self, pack: LibraryPackRow) -> None:
        """Update mutable metadata (pack_name/display_name/version) only.

        ``pack_uid``, ``system_name``, ``owner_world_uid`` and
        ``source_pack_uid`` are identity/provenance — never rewritten on
        an existing row (TZ §2).
        """
        ...

    @abstractmethod
    async def delete(self, pack_uid: str) -> None:
        """Delete the pack; members/dependencies cascade."""
        ...
