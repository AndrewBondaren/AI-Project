"""Shared library-template section handler — tz_world_bundle WB-9."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from app.application.imports.result import ImportResult
if TYPE_CHECKING:
    from app.application.templateLibrary.packs.write.writeResults import PolicyRequired
from app.application.templateLibrary.packs.errors import require_no_policy
from app.application.worldBundle.errors import BundleValidationError
from app.db.models.world import World
from app.application.jsonValidation.bundle.preflight import validate_rows
from app.application.jsonValidation.resolve import ResolveContext


@dataclass(frozen=True, slots=True)
class LibrarySectionAdapter:
    section_key: str
    export_bodies: Callable[[str], Awaitable[list[dict]]]
    import_bodies: Callable[[str, list[dict]], Awaitable[ImportResult | PolicyRequired]]
    prepare_body: Callable[..., Any]


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
        return require_no_policy(await self._adapter.import_bodies(world_uid, data))

    def validate_section(self, world: World, data: Any, *, ctx: ResolveContext) -> None:
        validate_rows(data, lambda row, row_ctx: self._adapter.prepare_body(
            world, row, ctx=row_ctx), ctx=ctx, contextual=True)
