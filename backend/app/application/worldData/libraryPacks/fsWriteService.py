"""FS input adapter; user writes use L-4, trusted defaults remain additive."""
from app.application.worldData.libraryPacks.defaults import is_default_pack_uid
from app.application.worldData.libraryPacks.fsWriteSource import read_fs_write_source
from app.application.worldData.libraryPacks.errors import LibraryPackConflictError
from app.application.worldData.libraryPacks.packResults import PackImportResult
from app.application.worldData.libraryPacks.writeContracts import LibraryWriteItem, LibraryWriteRequest, WriteSource
from app.application.worldData.libraryPacks.writeResults import WriteResult
from app.application.worldData.libraryPacks.writeFacade import require_result
from app.db.models.libraryPackDependency import LibraryPackDependencyRow
from app.ids import LibraryKind


class LibraryFsWriteService:
    def __init__(self, scope, writer):
        self._scope, self._writer = scope, writer

    async def import_path(self, kind, path, *, domain_root=None, enforce_domain_root=True,
                          decisions=(), preview_token=None):
        loaded = read_fs_write_source(kind, path, domain_root=domain_root,
                                      enforce_domain_root=enforce_domain_root)
        async with self._scope.db.transaction_if_needed():
            return await self._import_loaded(kind, loaded, decisions=decisions, preview_token=preview_token)

    async def _import_loaded(self, kind, loaded, *, decisions, preview_token):
        raw = loaded.source
        if is_default_pack_uid(raw.pack.pack_uid):
            return await self._canonical(raw)
        # New pack + one selected member must not import unselected bodies.
        existing = await self._scope.packs.get_by_uid(raw.pack.pack_uid) if loaded.single_member else None
        member_mode = loaded.single_member and existing is not None
        item = LibraryWriteItem(item_key="fs", object_kind="member" if member_mode else "pack",
            source=WriteSource(kind="import", key="fs"),
            target_pack_uid=raw.pack.pack_uid if member_mode else None,
            library_kind=LibraryKind(kind) if member_mode else None)
        result = require_result(await self._writer.execute(LibraryWriteRequest(items=(item,),
            decisions=tuple(decisions), preview_token=preview_token), imports={"fs": raw}))
        if not isinstance(result, WriteResult):
            return result
        pack = result.plan.items[0].pack
        pack = pack.value if pack else existing
        bodies = tuple([await self._scope.adapter_for(LibraryKind(w.value.member.library_kind)).find_body_row(
            w.value.member.template_uid) for w in result.plan.items[0].members])
        return PackImportResult(pack, bodies)

    async def _canonical(self, raw):
        scope = self._scope
        async with scope.db.transaction_if_needed():
            prepared = []
            for entry in raw.members:
                adapter = scope.adapter_for(LibraryKind(entry.member.library_kind))
                outline = adapter.prepare_body(entry.body, local_uid=entry.member.local_uid,
                    template_uid=entry.member.template_uid)
                current = await scope.members.get_by_uid(entry.member.template_uid)
                if current and current != entry.member:
                    raise LibraryPackConflictError("canonical membership identity occupied")
                prepared.append((entry, adapter, outline))
            await scope.packs.insert_missing([raw.pack])
            for entry, adapter, outline in prepared:
                if await adapter.read_body_row(entry.member.template_uid) is None:
                    await adapter.persist_prepared(outline, member=entry.member,
                                                  source_file=entry.source_file, added=True)
            await scope.members.insert_missing([e.member for e in raw.members])
            await scope.deps.insert_missing([LibraryPackDependencyRow(raw.pack.pack_uid, uid) for uid in raw.dependencies])
            bodies = tuple([await adapter.find_body_row(entry.member.template_uid)
                            for entry, adapter, _ in prepared])
            return PackImportResult(await scope.packs.get_by_uid(raw.pack.pack_uid), bodies,
                                    tuple(sorted(await scope.missing_uids(raw.pack.pack_uid))))
