"""Preview/recheck/apply orchestration; all writes share one caller UOW."""
from dataclasses import replace
from app.application.jsonValidation.resolve import ResolveContext, report_issues

from app.application.worldData.libraryPacks.domainAdapters import RemappedMember
from app.application.worldData.libraryPacks.errors import LibraryPackConflictError
from app.application.worldData.libraryPacks.reinstantiatePlan import prepare_update
from app.db.models.libraryPackDependency import LibraryPackDependencyRow
from app.ids import LibraryKind


async def reinstantiate(scope, source, instance, world, *, confirm=False, preview_token=None):
    preview = await prepare_update(scope, source, instance, world)
    report_issues(ResolveContext(), preview.resolve_issues)
    if not confirm or not preview_token or preview_token != preview.preview_token:
        return replace(preview, stale=bool(confirm and preview_token and preview_token != preview.preview_token))
    if preview.conflicts:
        raise LibraryPackConflictError(f"update has conflicts: {preview.conflicts}")
    per_kind = {}
    for p in preview.prepared:
        adapter = scope.adapter_for(LibraryKind(p.member.library_kind))
        fresh = await scope.worlds.get_by_id(world.world_uid)
        outline = await adapter.write_body(p.body, local_uid=p.member.local_uid,
                                          template_uid=p.member.template_uid, pack=instance,
                                          world=fresh, source_file=p.source_file)
        if p.added:
            await scope.members.insert(p.member)
        else:
            await scope.members.update_local_uid(p.member.template_uid, p.member.local_uid)
        per_kind.setdefault(p.member.library_kind, []).append(RemappedMember(p.member, outline))
    for uid in preview.removed:
        member = await scope.members.get_by_uid(uid)
        adapter = scope.adapter_for(LibraryKind(member.library_kind))
        fresh = await scope.worlds.get_by_id(world.world_uid)
        await adapter.drop_pointer(fresh, uid)
        await adapter.delete_body(uid)
        await scope.members.delete(uid)
    for kind, members in per_kind.items():
        fresh = await scope.worlds.get_by_id(world.world_uid)
        await scope.adapter_for(LibraryKind(kind)).remap_world_refs(fresh, preview.uid_map, members)
    updated = replace(instance, pack_name=source.pack_name, display_name=source.display_name,
                      version=source.version)
    await scope.packs.update_metadata(updated)
    await scope.deps.delete_for_pack(instance.pack_uid)
    await scope.deps.insert_missing([LibraryPackDependencyRow(instance.pack_uid, uid) for uid in preview.dependencies])
    return replace(preview, applied=True)
