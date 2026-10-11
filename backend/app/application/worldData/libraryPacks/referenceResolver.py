"""One membership-scoped reference index (TZ packs §1.2)."""
from __future__ import annotations

from dataclasses import replace

from app.application.jsonValidation.resolve import ResolveContext, report_issues
from app.application.jsonValidation.types import FieldPathError, ReferenceIssueContext, ReferenceIssueReason

from app.application.worldData.libraryPacks.lifecycleContracts import CatalogSnapshot, MemberRef
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.libraryPacks.membership import membership_pack_uids
from app.ids import LibraryKind


async def load_catalog(scope, world_uid: str | None) -> CatalogSnapshot:
    uids = await membership_pack_uids(scope.packs, world_uid)
    members = await scope.members.list_by_packs(uids)
    bodies, files = {}, {}
    for member in members:
        found = await scope.adapter_for(LibraryKind(member.library_kind)).read_body_row(member.template_uid)
        if found is None:
            raise LibraryPackValidationError(f"member '{member.template_uid}' has no body")
        bodies[member.template_uid], files[member.template_uid] = found
    return CatalogSnapshot({m.template_uid: m for m in members}, bodies, files)


def collect_refs(adapters, catalog: CatalogSnapshot, world=None) -> tuple[MemberRef, ...]:
    refs = []
    for uid, member in catalog.members.items():
        refs.extend(adapters[LibraryKind(member.library_kind)].body_refs(catalog.bodies[uid], uid))
    if world is not None:
        for adapter in adapters.values():
            refs.extend(adapter.world_refs(world))
    return tuple(refs)


def reference_index(refs, members):
    index, diagnostics = {}, []
    for ref in refs:
        member = members.get(ref.template_uid)
        if member is None or member.library_kind != ref.library_kind:
            diagnostics.append(FieldPathError(
                (ref.consumer, ref.path),
                f"unavailable {ref.library_kind}:{ref.template_uid} at {ref.reason}",
                code="LIBRARY_REFERENCE",
                reference=ReferenceIssueContext(
                    ReferenceIssueReason.KIND_MISMATCH if member else ReferenceIssueReason.UNKNOWN_TEMPLATE,
                    ref.library_kind, requested_template_uid=ref.template_uid,
                    owner_pack_uid=member.pack_uid if member else None, consumer=ref.consumer),
            ))
        else:
            index.setdefault(ref.template_uid, []).append(ref.reason)
    return ({uid: tuple(sorted(set(reasons))) for uid, reasons in index.items()},
            tuple(sorted(set(diagnostics), key=lambda issue: issue.message)))


async def contextualize_issues(scope, issues, world_uid):
    """Resolve known ownership without making unavailable members available."""
    known_members = {}
    for issue in issues:
        context = issue.reference
        uid = context.requested_template_uid
        if context.owner_pack_uid is None and uid and uid not in known_members:
            member = await scope.members.get_by_uid(uid)
            if member is not None:
                known_members[uid] = member
    return contextualize_reference_issues(issues, known_members, world_uid)


def contextualize_reference_issues(issues, known_members, world_uid):
    """Pure ownership diagnostics over already loaded membership."""
    result = []
    for issue in issues:
        context = issue.reference
        member = (known_members.get(context.requested_template_uid)
                  if context.owner_pack_uid is None and context.requested_template_uid else None)
        reason = context.reason
        if member is not None:
            reason = (ReferenceIssueReason.OWNER_UNAVAILABLE
                      if member.library_kind == context.domain else ReferenceIssueReason.KIND_MISMATCH)
        result.append(replace(issue, reference=replace(
            context, world_uid=world_uid, reason=reason,
            owner_pack_uid=member.pack_uid if member else context.owner_pack_uid)))
    return tuple(result)


def dependency_issues(pack_uid, missing, world_uid):
    return tuple(FieldPathError(
        ("library_packs", pack_uid, "dependencies", uid),
        f"missing dependency pack '{uid}'", code="LIBRARY_DEPENDENCY",
        reference=ReferenceIssueContext(ReferenceIssueReason.MISSING_DEPENDENCY,
                                        LibraryKind.LIBRARY_PACKS.value, world_uid,
                                        owner_pack_uid=pack_uid, dependency_pack_uid=uid,
                                        consumer=pack_uid),
    ) for uid in sorted(missing))


def pin_index(world, members):
    if world is None:
        return {}
    from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
    result = {}
    for raw in world.library_pins or []:
        pin = LibraryPinEntry.model_validate(raw)
        member = members.get(pin.template_uid)
        if member is not None and member.library_kind == pin.library_kind:
            result[pin.template_uid] = (f"world:{world.world_uid}:library_pins",)
    return result


async def member_usages(scope, member, world):
    catalog = await load_catalog(scope, None if world is None else world.world_uid)
    refs = collect_refs(scope.adapters, catalog, world)
    index, issues = reference_index(refs, catalog.members)
    issues = await contextualize_issues(scope, issues, None if world is None else world.world_uid)
    report_issues(ResolveContext(), issues)
    return list(index.get(member.template_uid, ())) + list(pin_index(world, catalog.members).get(member.template_uid, ()))
