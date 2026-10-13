"""Archive application boundary over the common library write pipeline (TZ §4)."""
from app.application.worldData.libraryPacks.archiveSources import archive_source, export_pack
from app.application.worldData.libraryPacks.packIdentity import instance_system_name
from app.application.worldData.libraryPacks.writeContracts import LibraryWriteItem, WriteSource, validated_write_request
from app.application.worldData.libraryPacks.writeFacade import require_result


class LibraryArchiveService:
    def __init__(self, scope, writer):
        self._scope, self._writer = scope, writer

    async def export_pack(self, uid):
        return await export_pack(self._scope, uid)

    def read_engine_archive(self, path):
        from app.application.worldData.bundle.archive import read_archive, BundleArchiveError
        from app.dataModel.worldBundle.bundleManifest import BundleKind
        from app.application.worldData.libraryPacks.archiveSources import pack_to_wire
        contents = read_archive(path)
        if contents.manifest.kind != BundleKind.LIBRARY_PACK:
            raise BundleArchiveError("library import requires a library_pack archive")
        return [pack_to_wire(p) for p in contents.library_packs]

    async def write_engine_archive(self, uid, *, path):
        from datetime import datetime, timezone
        from app.application.worldData.bundle.archive import write_archive
        from app.dataModel.worldBundle.bundleManifest import BundleKind, BundleManifest, BundleLibraryPackSource
        from app.application.worldData.libraryPacks.errors import LibraryPackOwnershipError
        row = await self._scope.packs.get_by_uid(uid)
        pack = await self.export_pack(uid)
        if row.owner_world_uid is not None:
            raise LibraryPackOwnershipError("publish a world-owned pack before engine archive export")
        root = BundleManifest(kind=BundleKind.LIBRARY_PACK, format_version=1, sections={},
            source=BundleLibraryPackSource(kind=BundleKind.LIBRARY_PACK, pack_uid=uid,
                exporter="AI Project", exported_at=datetime.now(timezone.utc)))
        return write_archive({}, root, path=path, library_packs=(pack,))

    async def export_world(self, world_uid):
        return tuple([await self.export_pack(pack.pack_uid)
                      for pack in sorted(await self._scope.packs.list_world_owned(world_uid),
                                         key=lambda p: p.pack_uid)])

    def sources(self, packs, *, source_owner, target_owner):
        imports, items = {}, []
        seen = set()
        for pack in packs:
            uid = pack.manifest.pack_uid
            if uid in seen:
                from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
                raise LibraryPackValidationError("duplicate archive pack UID")
            seen.add(uid)
            source = archive_source(pack, owner=source_owner, supported=self._scope.adapters)
            imports[uid] = source
            name = (instance_system_name(target_owner, source.pack.system_name)
                    if target_owner != source_owner else None)
            items.append(LibraryWriteItem(item_key=uid, object_kind="pack",
                source=WriteSource(kind="import", key=uid), owner_world_uid=target_owner,
                target_system_name=name))
        return imports, tuple(items)

    async def prepare_world(self, packs, *, source_owner, target_owner, decisions=(), preview_token=None):
        imports, items = self.sources(packs, source_owner=source_owner, target_owner=target_owner)
        request = validated_write_request(items=items, decisions=tuple(decisions), preview_token=preview_token)
        return require_result(await self._writer.prepare(request, imports=imports))

    async def apply(self, plan):
        return await self._writer.apply_prepared(plan)

    async def import_engine(self, packs, *, decisions=(), preview_token=None):
        imports, items = self.sources(packs, source_owner=None, target_owner=None)
        request = validated_write_request(items=items, decisions=tuple(decisions), preview_token=preview_token)
        return require_result(await self._writer.execute(request, imports=imports))

    def validate_bodies(self, packs, world):
        """Read-only domain validation for validate_only and preflight."""
        imports, _ = self.sources(packs, source_owner=world.world_uid, target_owner=world.world_uid)
        for source in imports.values():
            for entry in source.members:
                from app.ids import LibraryKind
                self._scope.adapter_for(LibraryKind(entry.member.library_kind)).prepare_body(entry.body,
                    template_uid=entry.member.template_uid, local_uid=entry.member.local_uid, world=world)
