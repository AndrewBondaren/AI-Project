"""Shared adapter mixins — body-row CRUD and registry pointer dual-write.

``_LibraryBodyMixin`` is the single library read/write shape over the
domain library service. ``_RegistryPointerMixin`` is the transitional
world-registry pointer dual-write (until step 5b): registry columns are
written through the world repository as raw rows — the same storage path
as ``prepare_import`` — because ``worlds.update`` would normalize the
column against the registry-entry POJO and reject non-pointer rows
(e.g. embedded plot layouts) that legitimately live there.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from app.application.worldData.libraryPacks.domainAdapters.contract import (
    _POINTER_UID_FIELD,
    DomainLibrary,
    RemappedMember,
)
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository


class _LibraryBodyMixin:
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


class _RegistryPointerMixin:
    """Shared world-registry pointer dual-write for uid-keyed registries."""

    registry_field: ClassVar[str]
    _world_repo: IWorldRepository

    def prepare_world_refs(self, world, uid_map, members, *, removed_uids=()):
        from copy import deepcopy
        from app.application.worldData.libraryPacks.domainAdapters.remapRefs import remap_pins
        result = deepcopy(world)
        remap_pins(result, uid_map)
        entries = [self.pointer_entry(rm.member, rm.outline).model_dump(mode="json") for rm in members]
        setattr(result, self.registry_field, self._registry_with_entries(
            result, uid_map, members, entries, removed_uids))
        return result

    async def ensure_pointer(
        self, world: World, member: LibraryPackMemberRow, outline: Any
    ) -> None:
        await self._swap_pointer(
            world,
            template_uid=member.template_uid,
            entry=self._pointer_entry(member, outline),
        )

    async def drop_pointer(self, world: World, template_uid: str) -> None:
        await self._swap_pointer(world, template_uid=template_uid, entry=None)

    async def remap_world_refs(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> None:
        self._rebuild_registry_field(world, uid_map, members)
        await self._world_repo.update(world)

    def _rebuild_registry_field(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> None:
        """Rebuild the pointer column in place — no repository write;
        domains with extra world-side fields update once themselves."""
        from app.application.worldData.libraryPacks.domainAdapters.remapRefs import remap_pins
        remap_pins(world, uid_map)
        setattr(
            world, self.registry_field,
            self._remapped_registry(world, uid_map, members),
        )

    def _remapped_registry(
        self,
        world: World,
        uid_map: Mapping[str, str],
        members: Sequence[RemappedMember],
    ) -> list:
        """Registry after instantiate: pointer rows aimed at source or new
        member uids are rebuilt; other rows (foreign pointers, embedded
        plot layouts) pass through untouched — raw-dict scan, not the
        resolved POJO, so non-pointer rows survive."""
        entries = [self._pointer_entry(rm.member, rm.outline).model_dump(mode="json") for rm in members]
        return self._registry_with_entries(world, uid_map, members, entries)

    def _registry_with_entries(self, world, uid_map, members, new_entries, removed_uids=()):
        drop = set(uid_map) | {rm.member.template_uid for rm in members} | set(removed_uids)
        entries = [
            row for row in (getattr(world, self.registry_field, None) or [])
            if not (isinstance(row, dict) and row.get(_POINTER_UID_FIELD) in drop)
        ]
        entries.extend(new_entries)
        return entries

    def _pointer_entry(self, member: LibraryPackMemberRow, outline: Any):
        """Registry entry for this member — declared by each domain."""
        raise NotImplementedError

    async def _swap_pointer(
        self, world: World, *, template_uid: str, entry: Any | None
    ) -> None:
        entries = [
            row
            for row in (getattr(world, self.registry_field, None) or [])
            if not (
                isinstance(row, dict)
                and row.get(_POINTER_UID_FIELD) == template_uid
            )
        ]
        if entry is not None:
            entries.append(entry.model_dump(mode="json"))
        setattr(world, self.registry_field, entries)
        await self._world_repo.update(world)
