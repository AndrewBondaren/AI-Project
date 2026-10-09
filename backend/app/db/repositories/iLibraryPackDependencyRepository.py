"""Interface for ``library_pack_dependencies`` — tz_template_library_packs §3.

``required_pack_uid`` is not an FK: it may name a not-yet-imported pack;
incompleteness is diagnosed by the caller, never blocked here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.db.models.libraryPackDependency import LibraryPackDependencyRow


class ILibraryPackDependencyRepository(ABC):

    @abstractmethod
    async def insert(self, dependency: LibraryPackDependencyRow) -> None:
        """Strict insert; PK/FK violations raise."""
        ...

    @abstractmethod
    async def insert_missing(self, dependencies: Sequence[LibraryPackDependencyRow]) -> int:
        """Atomic fill-missing: ``ON CONFLICT DO NOTHING`` on the composite PK.
        Returns the number of inserted rows."""
        ...

    @abstractmethod
    async def list_for_pack(self, pack_uid: str) -> list[LibraryPackDependencyRow]: ...

    @abstractmethod
    async def list_for_packs(self, pack_uids: Sequence[str]) -> list[LibraryPackDependencyRow]:
        """Dependencies of an explicit pack set — dependency-closure primitive (TZ §5)."""
        ...

    @abstractmethod
    async def required_uids(self, pack_uid: str) -> set[str]: ...

    @abstractmethod
    async def list_dependents(
        self,
        required_pack_uid: str,
    ) -> list[LibraryPackDependencyRow]:
        """Reverse lookup — packs that declare *required_pack_uid* as a
        dependency. Serves ``idx_library_pack_deps_required``: delete-impact
        diagnostics when a pack is still required by others (the column is
        not an FK, so rows may outlive the referenced pack)."""
        ...

    @abstractmethod
    async def delete(self, pack_uid: str, required_pack_uid: str) -> None: ...

    @abstractmethod
    async def delete_for_pack(self, pack_uid: str) -> int:
        """Remove all declared dependencies of a pack; returns the count."""
        ...
