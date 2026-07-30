"""IBundleSectionHandler — tz_world_bundle.md WB-1."""

from __future__ import annotations

from typing import Any, Protocol

from app.application.importResult import ImportResult
from app.db.models.world import World


class IBundleSectionHandler(Protocol):
    key: str

    async def export_section(
        self,
        world_uid: str,
        *,
        world: World | None = None,
    ) -> Any | None:
        """Wire payload for this section key, or None to omit."""
        ...

    async def import_section(self, world_uid: str, data: Any) -> ImportResult:
        ...
