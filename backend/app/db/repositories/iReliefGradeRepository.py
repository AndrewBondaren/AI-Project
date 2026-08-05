"""Relief grade instance/system persistence — tz_terrain_relief §8c."""

from __future__ import annotations

from typing import Protocol

from app.db.models.reliefGradeInstance import ReliefGradeInstanceRow
from app.db.models.reliefGradeSystem import ReliefGradeSystemRow


class IReliefGradeRepository(Protocol):
    async def upsert_instance(self, row: ReliefGradeInstanceRow) -> None: ...

    async def upsert_system(self, row: ReliefGradeSystemRow) -> None: ...

    async def list_instances_for_world(self, world_uid: str) -> list[ReliefGradeInstanceRow]: ...

    async def delete_instances_for_world(self, world_uid: str) -> None: ...
