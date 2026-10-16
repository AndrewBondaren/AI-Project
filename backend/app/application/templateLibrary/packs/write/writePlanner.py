"""Prepare approved library writes: identities → bodies → retention (TZ §0.3)."""
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy

from app.application.templateLibrary.packs.domainAdapters import PackDomainAdapter
from app.application.templateLibrary.packs.errors import LibraryPackConflictError, LibraryPackValidationError
from app.application.templateLibrary.packs.write.memberWritePlanner import MemberWritePlanner
from app.application.templateLibrary.packs.write.packWritePlanner import PackWritePlanner
from app.application.templateLibrary.packs.write.writeContracts import (
    WriteDecision, WriteObjectKind, WriteSnapshot, WriteSourceKind, WriteStatus,
)
from app.application.templateLibrary.packs.write.writePlanContracts import LibraryWritePlan
from app.application.templateLibrary.packs.write.writeRetentionPlanner import WriteRetentionPlanner
from app.ids import LibraryKind


class LibraryWritePlanner:
    """Orchestrate pure preparation; no repository or policy implementation."""

    def __init__(self, adapters: Mapping[LibraryKind, PackDomainAdapter]):
        self._adapters = dict(adapters)
        self._packs, self._members = PackWritePlanner(), MemberWritePlanner()
        self._retention = WriteRetentionPlanner(self._adapters)

    def prepare(self, snapshot: WriteSnapshot, decision: WriteDecision) -> LibraryWritePlan:
        self._validate_input(snapshot, decision)
        # All mutable domain inputs are detached before adapter transformations.
        snapshot = deepcopy(snapshot)
        inspection = snapshot.inspection
        facts = {f.item.item_key: f for f in snapshot.items}
        sources, scopes = dict(inspection.sources), {s.owner_world_uid: s for s in inspection.scopes}
        occupied = set(inspection.existing_member_uids)
        projections, occupied_packs = [], set()
        for action in decision.actions:
            fact = facts[action.item_key]
            job = self._packs if fact.item.object_kind is WriteObjectKind.PACK else self._members
            projection = job.project(fact, action, sources[action.item_key], scopes[fact.item.owner_world_uid], occupied)
            if fact.item.object_kind is WriteObjectKind.PACK:
                if projection.pack.pack_uid in occupied_packs:
                    raise LibraryPackConflictError("batch writes a pack twice")
                occupied_packs.add(projection.pack.pack_uid)
            projections.append(projection)
        uid_maps, pack_maps, world_maps = self._maps(projections, facts)
        items = []
        for projection in projections:
            fact = facts[projection.decision.item_key]
            scope = scopes[fact.item.owner_world_uid]
            if fact.item.object_kind is WriteObjectKind.PACK:
                items.append(self._packs.prepare(projection, scope, self._adapters,
                                                  uid_maps[scope.owner_world_uid], pack_maps[scope.owner_world_uid]))
            else:
                items.append(self._members.prepare(projection, scope, self._adapters))
        writes = [w.value.member.template_uid for item in items for w in item.members]
        if len(set(writes)) != len(writes):
            raise LibraryPackConflictError("batch writes a member twice")
        if {uid for item in items for uid in item.candidates} & set(writes):
            raise LibraryPackConflictError("batch both replaces pack composition and writes an excluded member")
        plan = self._retention.finish(snapshot, projections, items, world_maps)
        imported = {uid for item in plan.items
                    if facts[item.item_key].item.source.kind is WriteSourceKind.IMPORT
                    for uid in ([item.pack.value.pack_uid] if item.pack else [])
                    + [w.value.member.template_uid for w in item.members]}
        invalid_import = [issue for issue in plan.diagnostics if issue.reference.consumer in imported]
        if invalid_import:
            raise LibraryPackValidationError("; ".join(issue.message for issue in invalid_import))
        return deepcopy(plan)

    @staticmethod
    def _validate_input(snapshot, decision):
        if (decision.status is not WriteStatus.READY or decision.stale or decision.issues
                or decision.preview_token != snapshot.preview_token or snapshot.inspection is None):
            raise LibraryPackValidationError("planning requires a ready decision for this inspected snapshot")
        expected = {f.item.item_key for f in snapshot.items}
        selected = [a.item_key for a in decision.actions]
        if set(selected) != expected or len(selected) != len(expected):
            raise LibraryPackValidationError("planning requires exactly one action per inspected item")
        if any(f.issues for f in snapshot.items):
            raise LibraryPackValidationError("invalid inspection cannot be planned")

    @staticmethod
    def _maps(projections, facts):
        uid_maps, pack_maps, world_maps = defaultdict(dict), defaultdict(dict), defaultdict(dict)
        for p in projections:
            fact = facts[p.decision.item_key]
            if fact.item.object_kind is not WriteObjectKind.PACK:
                continue
            owner = p.owner_world_uid
            if p.source.pack.pack_uid in pack_maps[owner]:
                raise LibraryPackConflictError("ambiguous source pack mapping in one scope")
            pack_maps[owner][p.source.pack.pack_uid] = p.pack.pack_uid
            for source, target in p.uid_map:
                if source in uid_maps[owner] and uid_maps[owner][source] != target:
                    raise LibraryPackConflictError("ambiguous source member mapping in one scope")
                uid_maps[owner][source] = target
            if p.source.pack.owner_world_uid != owner:
                world_maps[owner].update(p.uid_map)
        return uid_maps, pack_maps, world_maps
