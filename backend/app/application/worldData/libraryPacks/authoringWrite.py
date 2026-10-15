"""Normalize authored bodies into a single negotiated, atomic member batch."""
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.libraryPacks.writeContracts import LibraryWriteItem, validated_write_request, WriteSource
from app.application.worldData.libraryPacks.writeFacade import require_result
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteImportMember, WriteImportSource
from app.application.worldData.libraryPacks.writeResults import PolicyRequired, WriteResult
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, UID_PART_SEPARATOR, library_uid


async def write_authored_bodies(service, kind, pack_uid, bodies, *, local_uid=None,
                                decisions=(), preview_token=None, source_file=None, world_uid=None) -> WriteResult | PolicyRequired:
    if not pack_uid:
        raise LibraryPackValidationError("body write requires owning pack_uid")
    if not isinstance(bodies, list) or not bodies or any(not isinstance(b, dict) for b in bodies):
        raise LibraryPackValidationError("expected a nonempty array of body objects")
    if kind is LibraryKind.STRUCTURE_TEMPLATES and (not local_uid or len(bodies) != 1):
        raise LibraryPackValidationError("structure write requires one body and declared local_uid")
    async with service._scope.db.transaction_if_needed():
        pack = await service.get_pack(pack_uid)
        sources, items = {}, []
        for index, body in enumerate(bodies):
            key = local_uid if kind is LibraryKind.STRUCTURE_TEMPLATES else body.get("system_name")
            if not isinstance(key, str) or not key.strip() or key != key.strip() or UID_PART_SEPARATOR in key:
                raise LibraryPackValidationError("invalid authored local_uid")
            if local_uid is not None and key != local_uid:
                raise LibraryPackValidationError("body system_name differs from declared local_uid")
            uid = library_uid(kind, key, pack_uid=pack_uid)
            # Model-A copies carry a minted UID in the body, not the authored
            # pack/local formula. Preserve that identity when editing a copy.
            member_uid = body.get("system_name") if kind is LibraryKind.STRUCTURE_TEMPLATES else uid
            member = await service._scope.members.get_by_uid(member_uid) if member_uid else None
            if member is not None and (member.pack_uid, member.library_kind, member.local_uid) != (pack_uid, kind.value, key):
                raise LibraryPackValidationError("body/member identity mismatch")
            member = member or LibraryPackMemberRow(uid, pack_uid, kind.value, key)
            item_key = str(index)
            sources[item_key] = WriteImportSource(pack, (WriteImportMember(member, body, source_file),))
            items.append(LibraryWriteItem(item_key=item_key, object_kind="member",
                source=WriteSource(kind="authoring", key=item_key), target_pack_uid=pack_uid,
                library_kind=kind, owner_world_uid=world_uid))
        return require_result(await service._write_service.execute(validated_write_request(items=tuple(items),
            decisions=tuple(decisions), preview_token=preview_token), imports=sources))
