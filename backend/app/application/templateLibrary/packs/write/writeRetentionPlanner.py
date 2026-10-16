"""Batch-wide retention and diagnostics over projected state (TZ §0.3/§1.2)."""
from collections import defaultdict
from dataclasses import asdict, replace

from app.application.worldData.libraryPacks.bodyDiff import body_diff
from app.application.worldData.libraryPacks.lifecycleContracts import (
    CatalogSnapshot,
    WORLD_CONSUMER_PREFIX,
)
from app.application.worldData.libraryPacks.domainAdapters.contract import RemappedMember
from app.application.worldData.libraryPacks.referenceResolver import (
    collect_refs, contextualize_reference_issues, dependency_issues, pin_index, reference_index,
)
from app.application.worldData.libraryPacks.reinstantiatePolicy import hold_candidates
from app.application.worldData.libraryPacks.writePlanContracts import LibraryWritePlan, WorldWrite
from app.ids import LibraryKind


class WriteRetentionPlanner:
    """Compute least reachable retention, then dependency/REF diagnostics."""

    def __init__(self, adapters):
        self._adapters = adapters

    def finish(self, snapshot, projections, items, world_maps) -> LibraryWritePlan:
        """Plan = per-scope composition: catalog → retain → deps → diagnose."""
        inspection = snapshot.inspection
        all_held, removed, worlds, diagnostics = {}, [], [], []
        by_key = {p.decision.item_key: p for p in projections}
        updated = {p.item_key: p for p in items}
        for scope in inspection.scopes:
            scoped = [item for item in items
                      if by_key[item.item_key].owner_world_uid == scope.owner_world_uid]
            projected = self._merged_catalog(scope, scoped)
            held, removed_rows = self._retain_scope(scope, scoped, projected, world_maps)
            all_held.update((uid, tuple(sorted(reasons))) for uid, reasons in held.items())
            removed.extend(removed_rows)
            final = self._resolve_dependencies(scope, scoped, held, updated)
            world = self._world(scope.world, final, world_maps.get(scope.owner_world_uid, {}))
            if scope.world is not None and world != scope.world:
                worlds.append(WorldWrite(scope.world, world,
                                         body_diff(asdict(scope.world), asdict(world))))
            diagnostics.extend(
                self._diagnose_scope(scope, inspection, projected, final, world, by_key))
        return LibraryWritePlan(snapshot.preview_token, tuple(updated[i.item_key] for i in items),
                                tuple(removed), tuple(sorted(all_held.items())), tuple(worlds),
                                tuple(dict.fromkeys(diagnostics)))

    @staticmethod
    def _merged_catalog(scope, scoped):
        """Scope members overlaid with the scoped writes — pre-retention view."""
        members = {m.member.template_uid: m.member for m in scope.members}
        bodies = {m.member.template_uid: m.body for m in scope.members}
        for item in scoped:
            for write in item.members:
                members[write.value.member.template_uid] = write.value.member
                bodies[write.value.member.template_uid] = write.value.body
        return CatalogSnapshot(members, bodies, {})

    def _retain_scope(self, scope, scoped, projected, world_maps):
        """Least reachable retention: unreferenced candidates are dropped
        from the projected catalog; returns ``(held, removed member rows)``."""
        members = projected.members
        candidates = {uid for item in scoped for uid in item.candidates}
        world = self._world(scope.world, scoped, world_maps.get(scope.owner_world_uid, {}))
        held = hold_candidates(
            collect_refs(self._adapters, projected, world) + tuple(scope.location_refs),
            members, candidates, pin_index(world, members))
        deleted = candidates - held.keys()
        removed = [members[uid] for uid in sorted(deleted)]
        for uid in deleted:
            del projected.members[uid]
            del projected.bodies[uid]
        return held, removed

    @staticmethod
    def _resolve_dependencies(scope, scoped, held, updated):
        """Rebuild each touched pack's dependency declaration and store the
        replacement into ``updated``; returns the final scoped items."""
        for item in scoped:
            if item.pack is None:
                continue
            deps = set(item.pack.dependencies)
            if item.preserved or any(uid in held for uid in item.candidates):
                deps.update(dict(scope.dependencies).get(item.pack.value.pack_uid, ()))
            deps.discard(item.pack.value.pack_uid)
            updated[item.item_key] = replace(item, pack=replace(item.pack, dependencies=tuple(sorted(deps))))
        return [updated[item.item_key] for item in scoped]

    def _diagnose_scope(self, scope, inspection, projected, final, world, by_key):
        """REF + dependency diagnostics over the finished scope view."""
        diagnostics = []
        available_packs = {p.pack_uid for p in scope.packs} | {i.pack.value.pack_uid for i in final if i.pack}
        refs = collect_refs(self._adapters, projected, world) + tuple(scope.location_refs)
        touched_packs = {item.pack.value.pack_uid for item in final if item.pack}
        touched_members = {write.value.member.template_uid for item in final for write in item.members}
        diagnosed = touched_members | {uid for uid, member in projected.members.items()
                                       if member.pack_uid in touched_packs}
        refs = tuple(ref for ref in refs if ref.consumer in diagnosed or ref.consumer.startswith(WORLD_CONSUMER_PREFIX))
        _, issues = reference_index(refs, projected.members)
        diagnostics.extend(contextualize_reference_issues(issues, {m.template_uid: m for m in inspection.known_members},
                                                          scope.owner_world_uid))
        graph = dict(inspection.dependency_edges)
        graph.update((item.pack.value.pack_uid, item.pack.dependencies) for item in final if item.pack)
        dependency_roots = {by_key[item.item_key].pack.pack_uid for item in final}
        for pack_uid in sorted(dependency_roots):
            diagnostics.extend(dependency_issues(pack_uid,
                self._missing_dependencies(pack_uid, graph, available_packs), scope.owner_world_uid))
        return diagnostics

    @staticmethod
    def _missing_dependencies(root, graph, available):
        missing, visited, pending = set(), set(), [root]
        while pending:
            uid = pending.pop()
            if uid in visited:
                continue
            visited.add(uid)
            for dependency in graph.get(uid, ()):
                if dependency not in available:
                    missing.add(dependency)
                else:
                    pending.append(dependency)
        return missing

    def _world(self, world, items, uid_map):
        """Project declared world-side refs for the written members.

        Invariants:
        - Domain projections are independent — ``sorted(kind.value)`` is
          determinism, not semantics; adapters must not rely on each
          other's column writes.
        - ``library_pins`` is a deliberate ``resolve_world_column``
          bypass: pin entries are validated straight into
          ``LibraryPinEntry`` dumps. Every other column an adapter
          changes must be known to ``resolve_world_column``.
        """
        if world is None:
            return None
        from copy import deepcopy
        result = deepcopy(world)
        by_kind = defaultdict(list)
        for item in items:
            for write in item.members:
                by_kind[LibraryKind(write.value.member.library_kind)].append(
                    RemappedMember(write.value.member, write.value.outline))
        for kind, adapter in sorted(self._adapters.items(), key=lambda entry: entry[0].value):
            result = adapter.prepare_world_refs(result, uid_map, by_kind[kind])
        from app.application.jsonValidation.resolve import ResolveContext
        from app.application.jsonValidation.worldColumnResolve import resolve_world_column
        for key, value in asdict(result).items():
            if value != getattr(world, key):
                if key == "library_pins":
                    from app.application.jsonValidation.resolve import UnresolvedModelError, resolve_model
                    from app.application.jsonValidation.types import ImportValidationError
                    from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
                    try:
                        result.library_pins = [resolve_model(LibraryPinEntry, pin,
                            ctx=ResolveContext(path_prefix=(key, index))).model_dump(mode="json")
                            for index, pin in enumerate(value)]
                    except UnresolvedModelError as exc:
                        raise ImportValidationError(list(exc.issues)) from exc
                    continue
                resolved = resolve_world_column(key, value, ResolveContext(), existing=result)
                for column, prepared in resolved.items():
                    setattr(result, column, prepared)
        return result
