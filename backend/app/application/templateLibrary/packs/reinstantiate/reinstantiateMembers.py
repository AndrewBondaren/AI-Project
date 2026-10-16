"""Pure identity matching and domain-body preparation for re-instantiate."""
from collections.abc import Mapping

from app.application.worldData.libraryPacks.bodyDiff import body_diff
from app.application.worldData.libraryPacks.domainAdapters import PackDomainAdapter
from app.application.worldData.libraryPacks.errors import LibraryPackConflictError
from app.application.worldData.libraryPacks.lifecycleContracts import (
    MemberProjection, PreparedMember, ReinstantiateSnapshot,
)
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, remapped_library_uid


def member_identity(source_members, current, instance_uid):
    """Match persisted provenance first; only new members use the ID formula."""
    managed = {}
    for member in current.values():
        if member.creation_kind == 'pack_copy' and member.source_template_uid is not None:
            if member.source_template_uid in managed:
                raise LibraryPackConflictError('multiple pack-copy members name the same source UID')
            managed[member.source_template_uid] = member
    uid_map = {
        src.template_uid: (managed[src.template_uid].template_uid if src.template_uid in managed
                           else remapped_library_uid(LibraryKind(src.library_kind),
                                                     target_pack_uid=instance_uid,
                                                     source_template_uid=src.template_uid))
        for src in source_members
    }
    return managed, uid_map


def prepare_members(snapshot: ReinstantiateSnapshot,
                    adapters: Mapping[LibraryKind, PackDomainAdapter]) -> MemberProjection:
    current = {uid: member for uid, member in snapshot.catalog.members.items()
               if member.pack_uid == snapshot.instance.pack_uid}
    managed, uid_map = member_identity(snapshot.source_members, current, snapshot.instance.pack_uid)
    prepared, conflicts = [], []
    for src in snapshot.source_members:
        uid = uid_map[src.template_uid]
        previous = managed.get(src.template_uid)
        if previous is None and uid in snapshot.known_members:
            conflicts.append(f"target UID '{uid}' already belongs to another member")
            continue
        if previous is not None and previous.library_kind != src.library_kind:
            conflicts.append(f"source kind changed for '{src.template_uid}'")
            continue
        member = LibraryPackMemberRow(uid, snapshot.instance.pack_uid, src.library_kind, src.local_uid,
                                      src.template_uid, 'pack_copy')
        adapter = adapters[LibraryKind(src.library_kind)]
        body = adapter.prepare_body(
            adapter.remap_body(snapshot.source_bodies[src.template_uid], template_uid=uid, uid_map=uid_map),
            local_uid=member.local_uid, template_uid=uid, world=snapshot.world,
        ).model_dump(mode='json')
        before = (adapter.prepare_body(snapshot.catalog.bodies[uid], local_uid=previous.local_uid,
                                       template_uid=uid).model_dump(mode='json')
                  if previous is not None else {})
        prepared.append(PreparedMember(member, body, snapshot.source_files[src.template_uid],
                                       previous is None, body_diff(before, body)))
    candidates = frozenset(member.template_uid for src_uid, member in managed.items()
                           if src_uid not in snapshot.source_bodies)
    return MemberProjection(current, tuple(prepared), uid_map, candidates, tuple(conflicts))
