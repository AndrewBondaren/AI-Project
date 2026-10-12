"""Legacy operation arguments/results translated to the common L-4 pipeline."""
from app.application.worldData.libraryPacks.defaults import is_default_pack_uid
from app.application.worldData.libraryPacks.errors import (
    LibraryPackConflictError, LibraryPackOwnershipError, LibraryPackReadOnlyError,
    LibraryPackValidationError,
)
from app.application.worldData.libraryPacks.lifecycleContracts import (
    MemberCopyResult, PreparedMember, ReinstantiatePreview,
)
from app.application.worldData.libraryPacks.packResults import PackRemapResult
from app.application.worldData.libraryPacks.writeContracts import (
    LibraryWriteItem, LibraryWriteRequest, LibraryWriteSelection, WriteSource, validated_write_request,
)
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteImportMember, WriteImportSource
from app.application.worldData.libraryPacks.writeResults import PolicyRequired, WriteRejected, WriteResult
from app.ids import LibraryKind


def require_result(outcome):
    if isinstance(outcome, WriteRejected):
        message = "; ".join(outcome.issues)
        if "default" in message:
            raise LibraryPackReadOnlyError(message)
        if "owner" in message or "scope" in message:
            raise LibraryPackOwnershipError(message)
        if "occupied" in message or "conflict" in message:
            raise LibraryPackConflictError(message)
        raise LibraryPackValidationError(message)
    return outcome


def pack_request(uid, owner, *, decisions=(), token=None):
    return validated_write_request(items=(LibraryWriteItem(item_key="pack", object_kind="pack",
        source=WriteSource(kind="catalog", key=uid), owner_world_uid=owner),),
        decisions=tuple(decisions), preview_token=token)


def lifecycle_preview(plan, *, source_uid, stale=False, applied=False):
    item = plan.items[0]
    return ReinstantiatePreview(pack_uid=item.pack.value.pack_uid, source_pack_uid=source_uid,
        preview_token=plan.preview_token, prepared=tuple(PreparedMember(w.value.member,
            w.value.body, w.value.source_file, w.added, w.changes) for w in item.members),
        removed=tuple(m.template_uid for m in plan.removed), held=dict(plan.held),
        preserved=item.preserved, uid_map=dict(item.uid_map),
        diagnostics=tuple(i.message for i in plan.diagnostics), applied=applied, stale=stale,
        metadata_changes=item.pack.changes, dependencies=item.pack.dependencies,
        resolve_issues=plan.diagnostics)


class LibraryWriteFacade:
    def __init__(self, scope, writer):
        self._scope, self._writer = scope, writer

    async def instantiate_negotiated(self, source, world_uid, *, decisions=(), preview_token=None) -> PackRemapResult | PolicyRequired:
        if source.owner_world_uid is not None or is_default_pack_uid(source.pack_uid):
            raise LibraryPackValidationError("only non-default engine packs instantiate into worlds")
        result = require_result(await self._writer.execute(pack_request(source.pack_uid, world_uid,
            decisions=decisions, token=preview_token)))
        return await self.remap_result(result) if isinstance(result, WriteResult) else result

    async def instantiate(self, source, world_uid, *, confirm=False, preview_token=None):
        if source.owner_world_uid is not None or is_default_pack_uid(source.pack_uid):
            raise LibraryPackValidationError("only non-default engine packs instantiate into worlds")
        existing = await self._scope.packs.find_instance(world_uid, source.pack_uid)
        decisions = (LibraryWriteSelection(item_key="pack", policy="replace", target_uid=existing.pack_uid),
                     ) if existing and confirm else ()
        result = require_result(await self._writer.execute(pack_request(source.pack_uid, world_uid,
            decisions=decisions, token=preview_token)))
        if isinstance(result, PolicyRequired):
            preview = next((p.plan for p in result.preview if p.plan is not None), None)
            if preview is None:
                return result
            return lifecycle_preview(preview, source_uid=source.pack_uid, stale=result.stale)
        if existing:
            return lifecycle_preview(result.plan, source_uid=source.pack_uid, applied=True)
        return await self.remap_result(result)

    async def publish(self, source, *, system_name=None, decisions=(), preview_token=None) -> PackRemapResult | PolicyRequired:
        if source.owner_world_uid is None:
            raise LibraryPackValidationError("copy_pack publishes world-owned packs")
        decisions = tuple(decisions)
        if decisions:
            if (len(decisions) != 1 or decisions[0].item_key != "pack"
                    or decisions[0].policy.value != "copy"
                    or system_name is not None and decisions[0].copy_system_name != system_name):
                raise LibraryPackValidationError("publish requires one consistent COPY selection")
        elif system_name:
            decisions = (LibraryWriteSelection(item_key="pack", policy="copy", copy_system_name=system_name),)
        result = require_result(await self._writer.execute(pack_request(source.pack_uid, None,
            decisions=decisions, token=preview_token)))
        return await self.remap_result(result) if isinstance(result, WriteResult) else result

    async def copy_member(self, source, target_uid, *, owner=None):
        request = LibraryWriteRequest(items=(LibraryWriteItem(item_key="member", object_kind="member",
            source=WriteSource(kind="catalog", key=source.template_uid), owner_world_uid=owner,
            target_pack_uid=target_uid, library_kind=LibraryKind(source.library_kind)),),
            decisions=(LibraryWriteSelection(item_key="member", policy="copy"),))
        result = require_result(await self._writer.execute_exact_member(request))
        return MemberCopyResult(result.plan.items[0].members[0].value.member,
                                tuple(i.message for i in result.plan.diagnostics))

    async def edit_member(self, member, pack, body, *, owner=None, source_file=None):
        raw = WriteImportSource(pack, (WriteImportMember(member, body, source_file),))
        request = LibraryWriteRequest(items=(LibraryWriteItem(item_key="member", object_kind="member",
            source=WriteSource(kind="authoring", key="edit"), owner_world_uid=owner,
            target_pack_uid=pack.pack_uid, library_kind=LibraryKind(member.library_kind)),),
            decisions=(LibraryWriteSelection(item_key="member", policy="replace", target_uid=member.template_uid),))
        result = require_result(await self._writer.execute_exact_member(request, imports={"edit": raw}))
        return result.plan.items[0].members[0].value.member

    async def create_member(self, pack, *, kind, local_uid, body, owner=None, source_file=None):
        from app.db.models.libraryPackMember import LibraryPackMemberRow
        from app.ids import library_uid
        member = LibraryPackMemberRow(library_uid(kind, local_uid, pack_uid=pack.pack_uid),
                                      pack.pack_uid, kind.value, local_uid)
        return await self.submit_member(member, pack, body, owner=owner, source_file=source_file)

    async def submit_member(self, member, pack, body, *, owner=None, source_file=None):
        from app.application.worldData.libraryPacks.errors import LibraryPackPolicyRequiredError
        raw = WriteImportSource(pack, (WriteImportMember(member, body, source_file),))
        request = LibraryWriteRequest(items=(LibraryWriteItem(item_key="member", object_kind="member",
            source=WriteSource(kind="authoring", key="create"), owner_world_uid=owner,
            target_pack_uid=pack.pack_uid, library_kind=LibraryKind(member.library_kind)),))
        outcome = require_result(await self._writer.execute(request, imports={"create": raw}))
        if isinstance(outcome, PolicyRequired):
            raise LibraryPackPolicyRequiredError(outcome)
        return outcome.plan.items[0].members[0].value.member

    async def remap_result(self, result):
        item = result.plan.items[0]
        return PackRemapResult(item.pack.value, tuple(w.value.member for w in item.members),
                               dict(item.uid_map),
                               tuple(sorted(await self._scope.missing_uids(item.pack.value.pack_uid))),
                               created=item.pack.added)
