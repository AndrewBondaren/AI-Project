"""Relief grade instance/system persistence — tz_terrain_relief §8c / R43."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from app.db.models.reliefGradeInstance import ReliefGradeInstanceRow
from app.db.models.reliefGradeSystem import ReliefGradeSystemRow


class IReliefGradeRepository(Protocol):
    def persist_session(self) -> AbstractAsyncContextManager[None]:
        """One Database.transaction() for a persist pass (R43)."""
        ...

    async def upsert_instance(self, row: ReliefGradeInstanceRow) -> None: ...

    async def upsert_system(self, row: ReliefGradeSystemRow) -> None: ...

    async def upsert_instances(self, rows: Sequence[ReliefGradeInstanceRow]) -> None: ...

    async def upsert_systems(self, rows: Sequence[ReliefGradeSystemRow]) -> None: ...

    async def list_instances_by_uids(
        self,
        world_uid: str,
        uids: Sequence[str],
    ) -> list[ReliefGradeInstanceRow]: ...

    async def list_systems_by_uids(
        self,
        world_uid: str,
        uids: Sequence[str],
    ) -> list[ReliefGradeSystemRow]: ...

    async def list_instances_for_world(self, world_uid: str) -> list[ReliefGradeInstanceRow]: ...

    async def delete_instances_for_world(self, world_uid: str) -> None: ...
