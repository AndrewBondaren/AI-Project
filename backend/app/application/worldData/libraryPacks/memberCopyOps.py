"""Independent member-copy inside one author scope (TZ packs §0.1)."""
from app.application.worldData.libraryPacks.errors import LibraryPackOwnershipError, LibraryPackValidationError
from app.application.worldData.libraryPacks.lifecycleContracts import MemberCopyResult
from app.application.worldData.libraryPacks.referenceResolver import load_catalog, reference_index
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, runtime_uid


async def copy_member(scope, members, source_uid, target_pack_uid, *, world_uid=None):
    source = await members.require_member(source_uid)
    source_pack = await members._require_pack(source.pack_uid)
    target = await members._require_pack(target_pack_uid)
    scope.require_writable(target)
    scope.require_owner_scope(target, world_uid)
    if source_pack.owner_world_uid != target.owner_world_uid:
        raise LibraryPackOwnershipError('member-copy cannot cross author scopes; copy the whole pack')
    adapter = scope.adapter_for(LibraryKind(source.library_kind))
    found = await adapter.read_body_row(source_uid)
    if found is None:
        raise LibraryPackValidationError(f"source member '{source_uid}' has no body")
    raw, source_file = found
    uid = runtime_uid()
    while await scope.members.get_by_uid(uid) is not None or await adapter.read_body_row(uid) is not None:
        uid = runtime_uid()
    world = await scope.world_for(target)
    # Only the copied body's own identity changes; references stay intact.
    body = adapter.prepare_body(adapter.remap_body(raw, template_uid=uid, uid_map={}),
                                local_uid=source.local_uid, template_uid=uid, world=world)
    member = LibraryPackMemberRow(uid, target.pack_uid, source.library_kind,
                                  source.local_uid, source_uid, 'member_copy')
    catalog = await load_catalog(scope, target.owner_world_uid)
    _, diagnostics = reference_index(adapter.body_refs(body.model_dump(mode='json'), uid), catalog.members)
    missing = await scope.diagnose_missing(target)
    diagnostics += tuple(f"missing dependency pack '{dep}'" for dep in sorted(missing))
    await adapter.write_body(body.model_dump(mode='json'), local_uid=member.local_uid,
                             template_uid=uid, pack=target, world=world, source_file=source_file)
    await scope.members.insert(member)
    if world is not None:
        await adapter.ensure_pointer(world, member, body)
    return MemberCopyResult(member, diagnostics)
