"""Shared adapter mixins — body-row CRUD over the domain library service.

``LibraryBodyMixin`` is the single library read/write shape over the
domain library service. The transitional registry pointer dual-write is
gone (B6): membership is the single availability source, so adapters no
longer write world registry columns — ``prepare_world_refs`` projections
only rewrite pins and declared ref fields.
"""

from __future__ import annotations

from app.application.worldData.libraryPacks.domainAdapters.contract import (
    DomainLibrary,
)


class LibraryBodyMixin:
    """Shared body-row CRUD over the domain library service."""

    _library: DomainLibrary

    async def find_body_row(self, template_uid):
        return await self._library.find_by_uid(template_uid)

    async def persist_prepared(self, outline, *, member, source_file, added):
        return await self._library.persist_prepared(outline, template_uid=member.template_uid,
                                                   source_file=source_file, added=added)

    async def read_body_row(
        self, template_uid: str
    ) -> tuple[dict, str | None] | None:
        row = await self._library.find_by_uid(template_uid)
        return None if row is None else (dict(row.data), row.source_file)

    async def delete_body(self, template_uid: str) -> None:
        if await self._library.find_by_uid(template_uid) is not None:
            await self._library.delete_prepared(template_uid)
