"""Strict prepared persistence; policy and transaction ownership stay above."""
from copy import deepcopy
import sqlite3

from app.application.worldData.libraryPacks.errors import LibraryPackConflictError
from app.application.worldData.libraryPacks.writeResults import WriteResult
from app.application.worldData.libraryPacks.writePlanContracts import LibraryWritePlan
from app.application.worldData.worldColumnWrite import apply_prepared_world_columns
from app.db.database import _in_transaction
from app.db.models.libraryPackDependency import LibraryPackDependencyRow
from app.ids import LibraryKind


class LibraryWriteExecutor:
    def __init__(self, *, db, catalog, adapters, world_repository):
        self._db, self._catalog = db, catalog
        self._adapters, self._worlds = dict(adapters), world_repository

    async def apply(self, plan: LibraryWritePlan) -> WriteResult:
        if (not _in_transaction.get() or not self._db.main_conn.in_transaction
                or not self._db.main_conn.owns_unit_of_work):
            raise RuntimeError("library executor requires caller main-connection UOW")
        await self._check(plan)
        world_writes = []
        for write in plan.worlds:
            world = await self._worlds.get_by_id(write.before.world_uid)
            keys = {change.path[0] for change in write.changes}
            if world is None or any(getattr(world, key) != getattr(write.before, key) for key in keys):
                raise LibraryPackConflictError("prepared world state changed before apply")
            world_writes.append((world, {
                key: deepcopy(getattr(write.after, key)) for key in keys}))
        try:
            for item in plan.items:
                if item.pack and item.pack.added:
                    await self._catalog.packs.insert(item.pack.value)
            for item in plan.items:
                for write in item.members:
                    value = write.value
                    adapter = self._adapters[LibraryKind(value.member.library_kind)]
                    await adapter.persist_prepared(value.outline, member=value.member,
                        source_file=value.source_file, added=write.added)
                    if write.added:
                        await self._catalog.members.insert(value.member)
                    else:
                        await self._catalog.members.update_local_uid(
                            value.member.template_uid, value.member.local_uid)
                if item.pack:
                    if not item.pack.added:
                        await self._catalog.packs.update_metadata(item.pack.value)
                    await self._catalog.deps.delete_for_pack(item.pack.value.pack_uid)
                    await self._catalog.deps.insert_missing([
                        LibraryPackDependencyRow(item.pack.value.pack_uid, uid)
                        for uid in item.pack.dependencies])
            for member in plan.removed:
                await self._adapters[LibraryKind(member.library_kind)].delete_body(member.template_uid)
                await self._catalog.members.delete(member.template_uid)
            for world, prepared in world_writes:
                apply_prepared_world_columns(world, prepared)
                await self._worlds.update(world)
        except sqlite3.IntegrityError as exc:
            raise LibraryPackConflictError(str(exc)) from exc
        return WriteResult(plan)

    async def _check(self, plan):
        for item in plan.items:
            if item.pack:
                current = await self._catalog.packs.get_by_uid(item.pack.value.pack_uid)
                named = await self._catalog.packs.get_by_system_name(item.pack.value.system_name)
                if item.pack.added and (current is not None or named is not None):
                    raise LibraryPackConflictError("new pack identity occupied")
                if not item.pack.added and (current is None or
                    (current.owner_world_uid, current.source_pack_uid) !=
                    (item.pack.value.owner_world_uid, item.pack.value.source_pack_uid)):
                    raise LibraryPackConflictError("replacement pack identity changed")
            for write in item.members:
                member = write.value.member
                current = await self._catalog.members.get_by_uid(member.template_uid)
                body = await self._adapters[LibraryKind(member.library_kind)].read_body_row(member.template_uid)
                if write.added and (current is not None or body is not None):
                    raise LibraryPackConflictError("new member/body identity occupied")
                if not write.added and (current is None or body is None or
                    (current.pack_uid, current.library_kind, current.source_template_uid, current.creation_kind) !=
                    (member.pack_uid, member.library_kind, member.source_template_uid, member.creation_kind)):
                    raise LibraryPackConflictError("replacement member/body identity changed")
