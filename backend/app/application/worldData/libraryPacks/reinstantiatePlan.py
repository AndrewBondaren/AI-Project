"""Prepare one immutable-in-use update projection, without persistence."""
from __future__ import annotations

from dataclasses import asdict, replace

from app.application.worldData.libraryPacks.bodyDiff import body_diff
from app.application.worldData.libraryPacks.errors import LibraryPackConflictError, LibraryPackValidationError
from app.application.worldData.libraryPacks.lifecycleContracts import PreparedMember, ReinstantiatePreview
from app.application.worldData.libraryPacks.referenceResolver import (
    CatalogSnapshot, collect_refs, load_catalog, pin_index, reference_index,
)
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, remapped_library_uid, state_fingerprint


def _significant(value):
    if isinstance(value, dict):
        return {key: _significant(item) for key, item in value.items()
                if key not in ('imported_at', 'source_file')}
    if isinstance(value, list):
        return [_significant(item) for item in value]
    return value


async def prepare_update(scope, source, instance, world):
    catalog = await load_catalog(scope, world.world_uid)
    current = {uid: m for uid, m in catalog.members.items() if m.pack_uid == instance.pack_uid}
    source_members = await scope.members.list_by_pack(source.pack_uid)
    source_bodies, source_files = {}, {}
    for src in source_members:
        found = await scope.adapter_for(LibraryKind(src.library_kind)).read_body_row(src.template_uid)
        if found is None:
            raise LibraryPackValidationError(f"source member '{src.template_uid}' has no body")
        source_bodies[src.template_uid], source_files[src.template_uid] = found
    managed = {}
    for m in current.values():
        if m.creation_kind == 'pack_copy' and m.source_template_uid is not None:
            if m.source_template_uid in managed:
                raise LibraryPackConflictError('multiple pack-copy members name the same source UID')
            managed[m.source_template_uid] = m
    uid_map = {
        src.template_uid: (managed[src.template_uid].template_uid if src.template_uid in managed
                           else remapped_library_uid(LibraryKind(src.library_kind),
                                                     target_pack_uid=instance.pack_uid,
                                                     source_template_uid=src.template_uid))
        for src in source_members
    }
    prepared, conflicts = [], []
    for src in source_members:
        uid = uid_map[src.template_uid]
        previous = managed.get(src.template_uid)
        if previous is None and await scope.members.get_by_uid(uid) is not None:
            conflicts.append(f"target UID '{uid}' already belongs to another member")
            continue
        if previous is not None and previous.library_kind != src.library_kind:
            conflicts.append(f"source kind changed for '{src.template_uid}'")
            continue
        member = LibraryPackMemberRow(uid, instance.pack_uid, src.library_kind, src.local_uid,
                                      src.template_uid, 'pack_copy')
        adapter = scope.adapter_for(LibraryKind(src.library_kind))
        body = adapter.prepare_body(
            adapter.remap_body(source_bodies[src.template_uid], template_uid=uid, uid_map=uid_map),
            local_uid=member.local_uid, template_uid=uid, world=world,
        ).model_dump(mode='json')
        before = (adapter.prepare_body(catalog.bodies[uid], local_uid=previous.local_uid,
                                       template_uid=uid).model_dump(mode='json')
                  if previous is not None else {})
        prepared.append(PreparedMember(member, body, source_files[src.template_uid],
                                       previous is None, body_diff(before, body)))
    source_uids = set(source_bodies)
    candidates = {m.template_uid for src_uid, m in managed.items() if src_uid not in source_uids}
    projected = CatalogSnapshot(dict(catalog.members), dict(catalog.bodies), dict(catalog.source_files))
    for p in prepared:
        projected.members[p.member.template_uid] = p.member
        projected.bodies[p.member.template_uid] = p.body
    # Include candidate bodies to resolve dependency chains, but do not treat
    # their outgoing edges as roots unless their consumer is retained.
    refs = collect_refs(scope, projected, world)
    held = hold_candidates(refs, projected.members, candidates, pin_index(world, projected.members))
    removed = candidates - held.keys()
    final_members = {uid: m for uid, m in projected.members.items() if uid not in removed}
    final_refs = tuple(ref for ref in refs if ref.consumer not in removed)
    _, diagnostics = reference_index(final_refs, final_members)
    source_deps = sorted(await scope.deps.required_uids(source.pack_uid))
    target_deps = sorted(await scope.deps.required_uids(instance.pack_uid))
    preserved = tuple(sorted(uid for uid, m in current.items() if m.creation_kind != 'pack_copy'))
    desired_deps = sorted(set(source_deps) | (set(target_deps) if held or preserved else set()))
    existing_deps = sorted(await scope.packs.existing_uids(desired_deps))
    diagnostics += tuple(f"missing dependency pack '{uid}'" for uid in desired_deps if uid not in existing_deps)
    fingerprint = state_fingerprint(_significant({
        'version': 1, 'source': asdict(source), 'instance': asdict(instance),
        'source_members': [asdict(m) for m in sorted(source_members, key=lambda m: m.template_uid)],
        'source_bodies': source_bodies, 'members': {uid: asdict(m) for uid, m in catalog.members.items()},
        'bodies': catalog.bodies, 'world': asdict(world),
        'source_deps': source_deps, 'target_deps': target_deps,
        'desired_deps': desired_deps, 'existing_deps': existing_deps,
        'held': {uid: sorted(reasons) for uid, reasons in held.items()},
        'removed': sorted(removed), 'conflicts': sorted(conflicts),
    }))
    preview = ReinstantiatePreview(
        instance.pack_uid, source.pack_uid, fingerprint, tuple(prepared), tuple(sorted(removed)),
        {uid: tuple(sorted(reasons)) for uid, reasons in held.items()},
        preserved, uid_map, diagnostics, conflicts=tuple(conflicts),
        metadata_changes=body_diff({key: getattr(instance, key) for key in ('pack_name', 'display_name', 'version')},
                                   {key: getattr(source, key) for key in ('pack_name', 'display_name', 'version')}),
        dependencies=tuple(desired_deps),
    )
    return preview


def hold_candidates(refs, members, candidates, pins):
    """Least reachable closure; a cycle with no root cannot retain itself."""
    held = {uid: list(reasons) for uid, reasons in pins.items() if uid in candidates}
    changed = True
    while changed:
        changed = False
        for ref in refs:
            target = members.get(ref.template_uid)
            if (ref.template_uid not in candidates or target is None
                    or target.library_kind != ref.library_kind):
                continue
            if ref.consumer not in candidates or ref.consumer in held:
                if ref.template_uid not in held:
                    held[ref.template_uid] = []
                    changed = True
                if ref.reason not in held[ref.template_uid]:
                    held[ref.template_uid].append(ref.reason)
    return held
