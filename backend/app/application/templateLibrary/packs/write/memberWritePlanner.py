"""Prepare one member action; policy has already been decided (packs TZ §0.3)."""
from copy import deepcopy
from dataclasses import replace

from app.application.templateLibrary.packs.write.bodyDiff import body_diff
from app.application.templateLibrary.packs.errors import LibraryPackConflictError
from app.application.templateLibrary.packs.write.writeContracts import WriteAction, WriteSourceKind
from app.application.templateLibrary.packs.write.writeInspectionContracts import InspectedMember
from app.application.templateLibrary.packs.write.writePlanContracts import MemberWrite, WriteItemPlan, WriteProjection
from app.ids import LibraryKind, library_uid, runtime_uid


def new_member_uid(occupied: set[str]) -> str:
    """Central allocator, once per plan. SQL uniqueness is rechecked at apply."""
    uid = runtime_uid()
    while uid in occupied:
        uid = runtime_uid()
    occupied.add(uid)
    return uid


class MemberWritePlanner:
    """Allocate one member identity and prepare its domain body."""

    def project(self, facts, action, source, state, occupied: set[str]) -> WriteProjection:
        pack = next(p for p in state.packs if p.pack_uid == facts.item.target_pack_uid)
        original = source.members[0]
        if action.action is WriteAction.REPLACE:
            target = next(m for m in state.members if m.member.template_uid == action.target_uid)
            row = deepcopy(target.member)
            if row.pack_uid != pack.pack_uid or row.library_kind != original.member.library_kind:
                raise LibraryPackConflictError("replacement member is outside its destination")
        elif action.action is WriteAction.COPY or facts.item.source.kind is WriteSourceKind.CATALOG:
            row = replace(original.member, template_uid=new_member_uid(occupied), pack_uid=pack.pack_uid,
                          source_template_uid=original.member.template_uid, creation_kind="member_copy")
        else:
            uid = (original.member.template_uid if original.member.pack_uid == pack.pack_uid
                   else library_uid(LibraryKind(original.member.library_kind), original.member.local_uid,
                                    pack_uid=pack.pack_uid))
            if uid in occupied:
                raise LibraryPackConflictError("member create identity is occupied")
            occupied.add(uid)
            row = replace(original.member, template_uid=uid, pack_uid=pack.pack_uid)
        # Single-member copy preserves all body references, including self refs.
        return WriteProjection(action, facts.item.owner_world_uid, source, pack, False,
                               ((original, row),), ((original.member.template_uid, row.template_uid),))

    def prepare(self, projection, state, adapters, uid_map=None) -> WriteItemPlan:
        before = {m.member.template_uid: m for m in state.members}
        writes = tuple(self.prepare_member(src, row, before.get(row.template_uid), adapters,
                                            state.world, uid_map or {})
                       for src, row in projection.members)
        return WriteItemPlan(projection.decision.item_key, None, writes, projection.uid_map)

    @staticmethod
    def prepare_member(source, row, previous, adapters, world, uid_map) -> MemberWrite:
        adapter = adapters[LibraryKind(row.library_kind)]
        body = adapter.remap_body(deepcopy(source.body), template_uid=row.template_uid,
                                  local_uid=row.local_uid, uid_map=uid_map)
        outline = adapter.prepare_body(body, local_uid=row.local_uid,
                                       template_uid=row.template_uid, world=deepcopy(world))
        wire = outline.model_dump(mode="json")
        value = InspectedMember(deepcopy(row), wire, outline, source.source_file)
        return MemberWrite(value, previous is None,
                           body_diff(previous.outline.model_dump(mode="json") if previous else {}, wire))
