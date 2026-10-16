"""Legacy domain entry points delegate to the pack boundary; no persistence here."""
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.ids import LibraryKind, library_uid


async def write_domain_body(service, kind, outline, *, pack_uid=None, template_uid=None,
                            source_file=None, world_uid=None, local_uid=None):
    if kind is LibraryKind.STRUCTURE_TEMPLATES:
        template_uid = str(outline.system_name)
    elif template_uid is None:
        if pack_uid is None:
            raise LibraryPackValidationError("body write requires owning pack; ownerless upsert is forbidden")
        template_uid = library_uid(kind, outline.system_name, pack_uid=pack_uid)
    member = await service._scope.members.get_by_uid(template_uid)
    if member is not None:
        if member.library_kind != kind.value or pack_uid is not None and member.pack_uid != pack_uid:
            raise LibraryPackValidationError("body/member identity mismatch")
        pack = await service.get_pack(member.pack_uid)
        await service._writes.submit_member(member, pack, outline.model_dump(mode="json"),
                                            owner=world_uid, source_file=source_file)
    else:
        if pack_uid is None:
            raise LibraryPackValidationError("new body requires owning pack")
        if kind is LibraryKind.STRUCTURE_TEMPLATES and local_uid is None:
            raise LibraryPackValidationError("new structure body requires declared member local_uid")
        expected_uid = library_uid(kind, local_uid or outline.system_name, pack_uid=pack_uid)
        if template_uid != expected_uid:
            raise LibraryPackValidationError("new body identity must match its declared pack/local key")
        await service.create_member(pack_uid, library_kind=kind, local_uid=local_uid or outline.system_name,
            body=outline.model_dump(mode="json"), source_file=source_file, world_uid=world_uid)
    return await service._scope.adapter_for(kind).find_body_row(template_uid)
