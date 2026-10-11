"""Prepare whole-pack identity/content; no persistence or policy (packs TZ §2)."""
from copy import deepcopy
from dataclasses import asdict, replace

from app.application.worldData.libraryPacks.bodyDiff import body_diff
from app.application.worldData.libraryPacks.errors import LibraryPackConflictError
from app.application.worldData.libraryPacks.memberWritePlanner import MemberWritePlanner, new_member_uid
from app.application.worldData.libraryPacks.packIdentity import instance_system_name, published_system_name
from app.application.worldData.libraryPacks.reinstantiateMembers import member_identity
from app.application.worldData.libraryPacks.writeContracts import WriteAction, WriteSourceKind
from app.application.worldData.libraryPacks.writePlanContracts import PackWrite, WriteItemPlan, WriteProjection
from app.ids import LibraryKind, library_uid, remapped_library_uid


class PackWritePlanner:
    """Allocate pack/member identities, then prepare all members together."""

    def project(self, facts, action, source, state, occupied: set[str]) -> WriteProjection:
        target = None
        if action.action is WriteAction.REPLACE:
            target = next(p for p in state.packs if p.pack_uid == action.target_uid)
            pack = replace(target, pack_name=source.pack.pack_name,
                           display_name=source.pack.display_name, version=source.pack.version)
        else:
            name = source.pack.system_name
            if action.action is WriteAction.COPY:
                name = action.copy_system_name
            elif facts.item.source.kind is WriteSourceKind.CATALOG:
                if source.pack.owner_world_uid is None and facts.item.owner_world_uid is not None:
                    name = instance_system_name(facts.item.owner_world_uid, name)
                elif source.pack.owner_world_uid is not None and facts.item.owner_world_uid is None:
                    name = published_system_name(name)
            uid = library_uid(LibraryKind.LIBRARY_PACKS, name)
            if any(p.pack_uid == uid or p.system_name == name for p in state.packs):
                raise LibraryPackConflictError("pack create identity is occupied")
            carrying = facts.item.source.kind is WriteSourceKind.IMPORT and action.action is WriteAction.CREATE
            pack = replace(source.pack, pack_uid=uid, system_name=name,
                           owner_world_uid=facts.item.owner_world_uid,
                           source_pack_uid=source.pack.source_pack_uid if carrying else source.pack.pack_uid)
        current = {m.member.template_uid: m.member for m in state.members if m.member.pack_uid == pack.pack_uid}
        related = target is not None and target.source_pack_uid == source.pack.pack_uid
        managed, related_map = member_identity([m.member for m in source.members], current, pack.pack_uid) if related else ({}, {})
        pairs, mapping = [], {}
        carrying = pack.pack_uid == source.pack.pack_uid
        for original in source.members:
            src = original.member
            allocated_new = False
            previous = current.get(src.template_uid) if carrying else managed.get(src.template_uid)
            if previous is not None:
                if previous.library_kind != src.library_kind:
                    raise LibraryPackConflictError("replacement changed a member domain")
                row = replace(previous, local_uid=src.local_uid)
            elif carrying:
                row = deepcopy(src)
            elif target is None or related:
                uid = related_map.get(src.template_uid) or remapped_library_uid(
                    LibraryKind(src.library_kind), target_pack_uid=pack.pack_uid, source_template_uid=src.template_uid)
                row = replace(src, template_uid=uid, pack_uid=pack.pack_uid,
                              source_template_uid=src.template_uid, creation_kind="pack_copy")
            else:
                # Replacing unrelated content must not invent pack-copy lineage.
                row = replace(src, template_uid=new_member_uid(occupied), pack_uid=pack.pack_uid,
                              source_template_uid=src.template_uid, creation_kind="member_copy")
                allocated_new = True
            if previous is None:
                if row.template_uid in occupied and not allocated_new:
                    raise LibraryPackConflictError("new pack member identity is occupied")
                occupied.add(row.template_uid)
            pairs.append((original, row))
            mapping[src.template_uid] = row.template_uid
        mapped = set(mapping.values())
        preserved = tuple(sorted(uid for uid, row in current.items()
                                 if uid not in mapped and (row.creation_kind == "member_copy"
                                     or related and row.creation_kind != "pack_copy")))
        candidates = tuple(sorted(current.keys() - mapped - set(preserved)))
        return WriteProjection(action, facts.item.owner_world_uid, source, pack, target is None,
                               tuple(pairs), tuple(sorted(mapping.items())), candidates, preserved)

    def prepare(self, projection, state, adapters, uid_map, pack_map) -> WriteItemPlan:
        before = {m.member.template_uid: m for m in state.members}
        writes = tuple(MemberWritePlanner.prepare_member(src, row, before.get(row.template_uid),
                                                         adapters, state.world, uid_map)
                       for src, row in projection.members)
        previous = next((p for p in state.packs if p.pack_uid == projection.pack.pack_uid), None)
        dependencies = tuple(sorted({pack_map.get(uid, uid) for uid in projection.source.dependencies}))
        pack = PackWrite(deepcopy(projection.pack), projection.pack_added, dependencies,
                         body_diff(asdict(previous) if previous else {}, asdict(projection.pack)))
        return WriteItemPlan(projection.decision.item_key, pack, writes, projection.uid_map,
                             projection.candidates, projection.preserved)
