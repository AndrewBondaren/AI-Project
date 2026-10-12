"""Normalize manifest-less bodies before the shared, atomic write boundary."""
from app.application.worldData.libraryPacks.legacyPack import legacy_member_row, legacy_pack_row
from app.application.worldData.libraryPacks.writeContracts import LibraryWriteItem, validated_write_request, WriteSource
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteImportMember, WriteImportSource
from app.application.worldData.libraryPacks.writeFacade import require_result


async def import_legacy_bodies(scope, writer, kind, world_uid, outlines, *, decisions=(), preview_token=None):
    pack = legacy_pack_row(world_uid)
    entries = tuple(WriteImportMember(legacy_member_row(kind, outline.system_name, world_uid=world_uid),
        outline.model_dump(mode="json"), "bundle") for outline in outlines)
    async with scope.db.transaction_if_needed():
        existing = await scope.packs.get_by_uid(pack.pack_uid)
        if existing is None:
            sources = {"legacy": WriteImportSource(pack, entries)}
            items = (LibraryWriteItem(item_key="legacy", object_kind="pack",
                source=WriteSource(kind="import", key="legacy"), owner_world_uid=world_uid),)
        else:
            sources = {str(i): WriteImportSource(existing, (entry,)) for i, entry in enumerate(entries)}
            items = tuple(LibraryWriteItem(item_key=str(i), object_kind="member",
                source=WriteSource(kind="import", key=str(i)), owner_world_uid=world_uid,
                target_pack_uid=pack.pack_uid, library_kind=kind) for i in range(len(entries)))
        return require_result(await writer.execute(validated_write_request(items=items,
            decisions=tuple(decisions), preview_token=preview_token), imports=sources))
