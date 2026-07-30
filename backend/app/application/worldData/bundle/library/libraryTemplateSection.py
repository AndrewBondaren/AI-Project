"""Shared library-template section handler — tz_world_bundle WB-9."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.application.importResult import ImportResult
from app.application.worldData.bundle.errors import BundleValidationError
from app.db.models.world import World


@dataclass(frozen=True, slots=True)
class LibrarySectionAdapter:
    section_key: str
    export_bodies: Callable[[str], Awaitable[list[dict]]]
    import_bodies: Callable[[str, list[dict]], Awaitable[ImportResult]]


class LibraryTemplateSectionHandler:
    def __init__(self, adapter: LibrarySectionAdapter) -> None:
        self._adapter = adapter

    @property
    def key(self) -> str:
        return self._adapter.section_key

    async def export_section(
        self,
        world_uid: str,
        *,
        world: World | None = None,
    ) -> list[dict]:
        return await self._adapter.export_bodies(world_uid)

    async def import_section(self, world_uid: str, data: Any) -> ImportResult:
        if not isinstance(data, list):
            raise BundleValidationError(f"{self.key} section must be an array")
        return await self._adapter.import_bodies(world_uid, data)
