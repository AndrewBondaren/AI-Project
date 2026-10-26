"""L-3 pure plans over real inspected SQLite state; no apply boundary."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from test_library_packs_4b import _ServiceCase, _RELIEF, _STRUCT, _plot_body, _relief_body
from app.application.templateLibrary.packs.errors import LibraryPackConflictError, LibraryPackValidationError
from app.application.templateLibrary.packs.lifecycleContracts import MemberRef
from app.application.templateLibrary.packs.packCatalog import PackCatalogRepos
from app.application.templateLibrary.packs.write import memberWritePlanner
from app.application.templateLibrary.packs.write.writeContracts import (
    LibraryWriteItem, LibraryWriteRequest, LibraryWriteSelection, WriteSource, WriteStatus,
)
from app.application.templateLibrary.packs.write.writeInspectionContracts import WriteImportMember, WriteImportSource
from app.application.templateLibrary.packs.write.writeInspector import LibraryWriteInspector
from app.application.templateLibrary.packs.write.writePlanner import LibraryWritePlanner
from app.application.templateLibrary.packs.write.writePolicy import LibraryWritePolicy
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, library_uid, remapped_library_uid, runtime_uid


_PLOT = LibraryKind.PLOT_TEMPLATES

class LibraryWritePlanTests(_ServiceCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self._world("w1")
        scope = self.service._scope
        self.inspector = LibraryWriteInspector(catalog=PackCatalogRepos(self.packs, self.members, self.deps),
                                               adapters=scope.adapters, worlds=scope.worlds)
        self.planner = LibraryWritePlanner(scope.adapters)

    def item(self, uid, *, key="entry", owner="w1", target=None, kind=None, imported=False):
        return LibraryWriteItem(item_key=key, object_kind="member" if target else "pack",
            source=WriteSource(kind="import" if imported else "catalog", key=uid),
            owner_world_uid=owner, target_pack_uid=target, library_kind=kind)

    async def ready(self, items, *, selections=(), imports=None):
        request = LibraryWriteRequest(items=tuple(items))
        snapshot = await self.inspector.inspect(request, imports=imports)
        if selections:
            request = request.model_copy(update={"decisions": tuple(selections), "preview_token": snapshot.preview_token})
            snapshot = await self.inspector.inspect(request, imports=imports)
        decision = LibraryWritePolicy().decide(snapshot, request)
        self.assertEqual(decision.status, WriteStatus.READY, decision)
        return snapshot, decision

    async def plan(self, items, **kwargs):
        snapshot, decision = await self.ready(items, **kwargs)
        saved = deepcopy(snapshot)
        trace = []
        await self.db.main_conn.set_trace_callback(trace.append)
        try:
            result = self.planner.prepare(snapshot, decision)
        finally:
            await self.db.main_conn.set_trace_callback(None)
        self.assertEqual(snapshot, saved)
        self.assertEqual(trace, [])
        return result

    def select(self, *, key="entry", target=None, copy_name=None):
        return LibraryWriteSelection(item_key=key, policy="replace" if target else "copy",
                                     target_uid=target, copy_system_name=copy_name)

    def imported(self, name="import.fresh", *, owner="w1", local="meadow", kind=_RELIEF, body=None,
                 dependencies=()):
        uid = library_uid(LibraryKind.LIBRARY_PACKS, name)
        pack = LibraryPackRow(uid, name, "folder", "Imported", owner_world_uid=owner)
        member = LibraryPackMemberRow(library_uid(kind, local, pack_uid=uid), uid, kind.value, local)
        return WriteImportSource(pack, (WriteImportMember(member, body or _relief_body(local)),), dependencies)

    async def test_import_create_carries_pack_member_identity_and_lineage(self):
        raw = self.imported()
        plan = await self.plan([self.item("raw", imported=True)], imports={"raw": raw})
        item = plan.items[0]
        self.assertEqual(item.pack.value, raw.pack)
        self.assertEqual(item.members[0].value.member, raw.members[0].member)
        self.assertTrue(item.pack.added)
        self.assertTrue(item.members[0].added)
        self.assertFalse(plan.diagnostics)

    async def test_member_import_create_rekeys_only_when_destination_changes(self):
        pack = await self.service.create_pack(system_name="world.target", owner_world_uid="w1")
        raw = self.imported()
        plan = await self.plan([self.item("raw", imported=True, target=pack.pack_uid, kind=_RELIEF)], imports={"raw": raw})
        row = plan.items[0].members[0].value.member
        self.assertEqual(row.template_uid, library_uid(_RELIEF, "meadow", pack_uid=pack.pack_uid))
        self.assertEqual(row.pack_uid, pack.pack_uid)
        self.assertIsNone(plan.items[0].pack)

    async def test_member_replace_keeps_exact_target_key_identity_and_provenance(self):
        pack = await self.service.create_pack(system_name="world.target", owner_world_uid="w1")
        source = await self.service.create_member(pack.pack_uid, library_kind=_RELIEF, local_uid="source",
                                                  body=_relief_body("source"), world_uid="w1")
        target = await self.service.copy_member(source.template_uid, pack.pack_uid, world_uid="w1")
        raw = self.imported(local="source", body=_relief_body("source", display_name="Revision"))
        plan = await self.plan([self.item("raw", imported=True, target=pack.pack_uid, kind=_RELIEF)],
            selections=[self.select(target=target.member.template_uid)], imports={"raw": raw})
        write = plan.items[0].members[0]
        self.assertEqual(write.value.member, target.member)
        self.assertEqual(write.value.body["display_name"], "Revision")
        self.assertTrue(write.changes)
        self.assertFalse(write.added)

    async def test_member_uid_match_preserves_target_key_after_source_key_change(self):
        pack = await self.service.create_pack(system_name="world.target", owner_world_uid="w1")
        target = await self.service.create_member(pack.pack_uid, library_kind=_RELIEF, local_uid="old",
                                                  body=_relief_body("old"), world_uid="w1")
        raw = WriteImportSource(pack, (WriteImportMember(replace(target, local_uid="new"), _relief_body("new")),))
        plan = await self.plan([self.item("raw", imported=True, target=pack.pack_uid, kind=_RELIEF)],
            selections=[self.select(target=target.template_uid)], imports={"raw": raw})
        self.assertEqual(plan.items[0].members[0].value.member.local_uid, "old")
        self.assertEqual(plan.items[0].members[0].value.body["system_name"], "old")

    async def test_member_copy_preserves_source_refs_and_world_consumers(self):
        pack = await self.service.create_pack(system_name="world.graph", owner_world_uid="w1")
        structure = await self.service.create_member(pack.pack_uid, library_kind=_STRUCT, local_uid="house",
                                                     body={"display_name": "House"}, world_uid="w1")
        plot = await self.service.create_member(pack.pack_uid, library_kind=_PLOT, local_uid="plot",
                                                body=_plot_body("plot", structure.template_uid), world_uid="w1")
        plan = await self.plan([self.item(plot.template_uid, target=pack.pack_uid, kind=_PLOT)],
                               selections=[self.select()])
        copied = plan.items[0].members[0]
        self.assertNotEqual(copied.value.member.template_uid, plot.template_uid)
        self.assertEqual(copied.value.body["main_building"]["structure"], structure.template_uid)
        self.assertEqual(copied.value.member.creation_kind, "member_copy")
        self.assertEqual(copied.value.member.source_template_uid, plot.template_uid)
        for world in plan.worlds:
            self.assertEqual(world.before.library_pins, world.after.library_pins)

    async def test_structure_copy_embeds_new_uid_model_a(self):
        pack = await self.service.create_pack(system_name="world.structure", owner_world_uid="w1")
        source = await self.service.create_member(pack.pack_uid, library_kind=_STRUCT, local_uid="house",
                                                  body={"display_name": "House"}, world_uid="w1")
        plan = await self.plan([self.item(source.template_uid, target=pack.pack_uid, kind=_STRUCT)],
                               selections=[self.select()])
        write = plan.items[0].members[0]
        self.assertEqual(write.value.body["system_name"], write.value.member.template_uid)

    async def test_pack_copy_keeps_repeated_local_keys_separate_and_external_refs(self):
        source = await self.service.create_pack(system_name="world.source", owner_world_uid="w1")
        external = await self.service.create_pack(system_name="world.external", owner_world_uid="w1")
        ext = await self.service.create_member(external.pack_uid, library_kind=_STRUCT, local_uid="outside",
                                               body={"display_name": "Outside"}, world_uid="w1")
        structure = await self.service.create_member(source.pack_uid, library_kind=_STRUCT, local_uid="house",
                                                     body={"display_name": "House"}, world_uid="w1")
        duplicate = await self.service.copy_member(structure.template_uid, source.pack_uid, world_uid="w1")
        plot = await self.service.create_member(source.pack_uid, library_kind=_PLOT, local_uid="plot",
            body=_plot_body("plot", structure.template_uid, secondary_buildings=[{"structure": ext.template_uid}]), world_uid="w1")
        await self.service.set_dependencies(source.pack_uid, [external.pack_uid], world_uid="w1")
        plan = await self.plan([self.item(source.pack_uid)], selections=[self.select(copy_name="world.copy")])
        item = plan.items[0]
        mapping = dict(item.uid_map)
        self.assertNotEqual(mapping[structure.template_uid], mapping[duplicate.member.template_uid])
        self.assertEqual(item.pack.dependencies, (external.pack_uid,))
        body = next(w.value.body for w in item.members if w.value.member.source_template_uid == plot.template_uid)
        self.assertEqual(body["main_building"]["structure"], mapping[structure.template_uid])
        self.assertEqual(body["secondary_buildings"][0]["structure"], ext.template_uid)
        self.assertTrue(all(w.value.member.creation_kind == "pack_copy" for w in item.members))

    async def test_cross_scope_pack_create_remaps_world_pins_and_pick_policy_purely(self):
        source, rows = await self._relief_engine_pack(members=("meadow",))
        world = await self.worlds.get_by_id("w1")
        world.library_pins = [{"library_kind": _RELIEF.value, "template_uid": rows[0].template_uid}]
        world.relief_pick_policy = {"open_land": {"default_template_uid": rows[0].template_uid}}
        await self.worlds.update(world)
        plan = await self.plan([self.item(source.pack_uid)])
        item = plan.items[0]
        self.assertEqual(item.pack.value.source_pack_uid, source.pack_uid)
        self.assertEqual(item.pack.value.system_name, "world.w1.instance." + source.system_name)
        target = dict(item.uid_map)[rows[0].template_uid]
        self.assertEqual(target, remapped_library_uid(_RELIEF, target_pack_uid=item.pack.value.pack_uid,
                                                    source_template_uid=rows[0].template_uid))
        projected = plan.worlds[0].after
        self.assertEqual(projected.library_pins[0]["template_uid"], target)
        self.assertEqual(projected.relief_pick_policy["open_land"]["default_template_uid"], target)
        # B7: the projected world rebuilds pins/policy only.
        self.assertEqual(await self.worlds.get_by_id("w1"), world)

    async def test_same_scope_independent_copy_does_not_repoint_world(self):
        source = await self.service.create_pack(system_name="world.relief", owner_world_uid="w1")
        row = await self.service.create_member(source.pack_uid, library_kind=_RELIEF, local_uid="meadow",
                                               body=_relief_body("meadow"), world_uid="w1")
        world = await self.worlds.get_by_id("w1")
        world.library_pins = [{"library_kind": _RELIEF.value, "template_uid": row.template_uid}]
        world.relief_pick_policy = {"open_land": {"default_template_uid": row.template_uid}}
        await self.worlds.update(world)
        plan = await self.plan([self.item(source.pack_uid)], selections=[self.select(copy_name="world.copy")])
        # B6: an in-scope copy no longer mints a world write at all.
        self.assertEqual(tuple(plan.worlds), ())
        saved = await self.worlds.get_by_id("w1")
        self.assertEqual(saved.library_pins, world.library_pins)
        self.assertEqual(saved.relief_pick_policy, world.relief_pick_policy)

    async def test_catalog_pack_self_replace_preserves_all_member_uids(self):
        source, rows = await self._relief_engine_pack()
        plan = await self.plan([self.item(source.pack_uid, owner=None)],
                               selections=[self.select(target=source.pack_uid)])
        self.assertEqual({w.value.member.template_uid for w in plan.items[0].members}, {r.template_uid for r in rows})
        self.assertFalse(plan.removed)
        self.assertFalse(any(w.changes for w in plan.items[0].members))

    async def test_batch_remaps_cross_pack_refs_and_dependencies_after_allocation(self):
        structures = await self.service.create_pack(system_name="engine.structures")
        building = await self.service.create_pack(system_name="engine.buildings")
        row = await self.service.create_member(structures.pack_uid, library_kind=_STRUCT, local_uid="house",
                                               body={"display_name": "House"})
        await self.service.create_member(building.pack_uid, library_kind=_PLOT, local_uid="plot",
                                          body=_plot_body("plot", row.template_uid))
        await self.service.set_dependencies(building.pack_uid, [structures.pack_uid])
        plan = await self.plan([self.item(building.pack_uid, key="b"), self.item(structures.pack_uid, key="s")])
        b, s = plan.items
        self.assertEqual(b.pack.dependencies, (s.pack.value.pack_uid,))
        self.assertEqual(b.members[0].value.body["main_building"]["structure"], s.members[0].value.member.template_uid)
        self.assertFalse(plan.diagnostics)

    async def test_import_unavailable_reference_rejected_catalog_reports_diagnostic(self):
        missing = runtime_uid()
        raw = self.imported(local="plot", kind=_PLOT, body=_plot_body("plot", missing))
        snapshot, decision = await self.ready([self.item("raw", imported=True)], imports={"raw": raw})
        with self.assertRaises(LibraryPackValidationError):
            self.planner.prepare(snapshot, decision)
        source = await self.service.create_pack(system_name="engine.broken")
        await self.service.create_member(source.pack_uid, library_kind=_PLOT, local_uid="plot",
                                          body=_plot_body("plot", missing))
        plan = await self.plan([self.item(source.pack_uid)])
        self.assertTrue(any(i.code == "LIBRARY_REFERENCE" for i in plan.diagnostics))

    async def test_import_transitive_missing_dependency_is_rejected(self):
        dependency = await self.service.create_pack(system_name="world.dep", owner_world_uid="w1")
        absent = runtime_uid()
        # Corrupt legacy dependency graph is diagnostic input, never silently repaired.
        snapshot, decision = await self.ready([self.item("raw", imported=True)],
            imports={"raw": self.imported(dependencies=(dependency.pack_uid,))})
        state = replace(snapshot.inspection,
                        dependency_edges=((dependency.pack_uid, (absent,)),))
        with self.assertRaisesRegex(LibraryPackValidationError, "missing dependency"):
            self.planner.prepare(replace(snapshot, inspection=state), decision)

    async def test_existing_world_broken_ref_appears_in_plan_diagnostics(self):
        source, _ = await self._relief_engine_pack()
        world = await self.worlds.get_by_id("w1")
        world.relief_pick_policy = {"open_land": {"default_template_uid": runtime_uid()}}
        await self.worlds.update(world)
        plan = await self.plan([self.item(source.pack_uid)])
        self.assertTrue(any(i.reference.consumer.startswith("world:") for i in plan.diagnostics))

    async def test_unready_stale_invalid_and_readonly_decisions_do_not_plan(self):
        source, _ = await self._relief_engine_pack()
        request = LibraryWriteRequest(items=(self.item(source.pack_uid, owner=None),))
        snapshot = await self.inspector.inspect(request)
        pending = LibraryWritePolicy().decide(snapshot, request)
        for decision in (pending, replace(pending, status=WriteStatus.READY, stale=True),
                         replace(pending, status=WriteStatus.READY, preview_token="different")):
            with self.assertRaises(LibraryPackValidationError):
                self.planner.prepare(snapshot, decision)
        target = replace(snapshot.items[0].destination, writable=False)
        readonly = replace(snapshot, items=(replace(snapshot.items[0], destination=target),))
        rejected = LibraryWritePolicy().decide(readonly, request)
        with self.assertRaises(LibraryPackValidationError):
            self.planner.prepare(readonly, rejected)

    async def test_runtime_allocator_retries_occupied_uid_and_fixes_uid_once(self):
        pack = await self.service.create_pack(system_name="world.member", owner_world_uid="w1")
        source = await self.service.create_member(pack.pack_uid, library_kind=_RELIEF, local_uid="meadow",
                                                  body=_relief_body("meadow"), world_uid="w1")
        fresh = runtime_uid()
        with patch(memberWritePlanner.__name__ + ".runtime_uid",
                   side_effect=[source.template_uid, fresh]) as allocator:
            plan = await self.plan([self.item(source.template_uid, target=pack.pack_uid, kind=_RELIEF)],
                                   selections=[self.select()])
        self.assertEqual(allocator.call_count, 2)
        self.assertEqual(plan.items[0].members[0].value.member.template_uid, fresh)

    async def test_ambiguous_source_to_two_pack_targets_rejected(self):
        source, _ = await self._relief_engine_pack()
        snapshot, decision = await self.ready([self.item(source.pack_uid, key="a"), self.item(source.pack_uid, key="b")],
            selections=[self.select(key="a", copy_name="copy.a"), self.select(key="b", copy_name="copy.b")])
        with self.assertRaisesRegex(LibraryPackConflictError, "ambiguous source pack"):
            self.planner.prepare(snapshot, decision)

    async def graph(self):
        pack = await self.service.create_pack(system_name="world.graph", owner_world_uid="w1")
        structure = await self.service.create_member(pack.pack_uid, library_kind=_STRUCT, local_uid="house",
                                                     body={"display_name": "House"}, world_uid="w1")
        plot = await self.service.create_member(pack.pack_uid, library_kind=_PLOT, local_uid="plot",
                                                body=_plot_body("plot", structure.template_uid), world_uid="w1")
        return pack, structure, plot

    async def empty_replace(self, pack, **kwargs):
        return await self.plan([self.item("raw", imported=True)],
            selections=[self.select(target=pack.pack_uid)], imports={"raw": WriteImportSource(pack, ())}, **kwargs)

    async def test_empty_pack_replace_removes_unrooted_composition(self):
        pack, structure, plot = await self.graph()
        plan = await self.empty_replace(pack)
        self.assertEqual({r.template_uid for r in plan.removed}, {structure.template_uid, plot.template_uid})
        self.assertFalse(plan.held)
        self.assertFalse(plan.worlds)  # Modern plot members create no legacy pointers.

    async def test_pin_retains_removed_candidate_and_its_dependencies(self):
        pack, structure, plot = await self.graph()
        world = await self.worlds.get_by_id("w1")
        world.library_pins = [{"library_kind": _PLOT.value, "template_uid": plot.template_uid}]
        await self.worlds.update(world)
        dependency = await self.service.create_pack(system_name="world.dependency", owner_world_uid="w1")
        await self.service.set_dependencies(pack.pack_uid, [dependency.pack_uid], world_uid="w1")
        plan = await self.empty_replace(pack)
        self.assertEqual(set(dict(plan.held)), {structure.template_uid, plot.template_uid})
        self.assertFalse(plan.removed)
        self.assertEqual(plan.items[0].pack.dependencies, (dependency.pack_uid,))

    async def test_independent_member_extra_is_preserved_and_roots_retention(self):
        pack, structure, plot = await self.graph()
        copied = await self.service.copy_member(plot.template_uid, pack.pack_uid, world_uid="w1")
        plan = await self.empty_replace(pack)
        self.assertEqual(plan.items[0].preserved, (copied.member.template_uid,))
        self.assertEqual(set(dict(plan.held)), {structure.template_uid})
        self.assertEqual([r.template_uid for r in plan.removed], [plot.template_uid])

    async def test_related_pack_replace_preserves_authored_and_member_copy_extras(self):
        source, rows = await self._relief_engine_pack(members=("meadow",))
        result = await self.service.instantiate_pack(source.pack_uid, world_uid="w1")
        authored = await self.service.create_member(result.pack.pack_uid, library_kind=_RELIEF, local_uid="extra",
                                                    body=_relief_body("extra"), world_uid="w1")
        independent = await self.service.copy_member(authored.template_uid, result.pack.pack_uid, world_uid="w1")
        await self.service.update_member_body(rows[0].template_uid, _relief_body("meadow", display_name="Revision"))
        plan = await self.plan([self.item(source.pack_uid)], selections=[self.select(target=result.pack.pack_uid)])
        item = plan.items[0]
        self.assertEqual(set(item.preserved), {authored.template_uid, independent.member.template_uid})
        self.assertEqual(item.members[0].value.member, result.members[0])
        self.assertEqual(item.members[0].value.body["display_name"], "Revision")
        self.assertTrue(item.members[0].changes)

    async def test_carried_pack_revision_preserves_target_lineage(self):
        source, _ = await self._relief_engine_pack(system_name="source.one")
        result = await self.service.instantiate_pack(source.pack_uid, world_uid="w1")
        raw = self.imported(name=result.pack.system_name)
        raw = replace(raw, pack=replace(raw.pack, source_pack_uid=runtime_uid()))
        plan = await self.plan([self.item("raw", imported=True)],
            selections=[self.select(target=result.pack.pack_uid)], imports={"raw": raw})
        # Carrying a recorded pack identity is a same-pack revision, preserving row lineage.
        self.assertEqual(plan.items[0].pack.value.source_pack_uid, source.pack_uid)
        self.assertEqual(plan.items[0].pack.value.system_name, result.pack.system_name)
        self.assertEqual(plan.items[0].members[0].value.member, raw.members[0].member)

    async def test_unrelated_pack_replace_uses_independent_members(self):
        source, rows = await self._relief_engine_pack()
        target = await self.service.create_pack(system_name="world.w1.instance." + source.system_name,
                                                owner_world_uid="w1")
        old = await self.service.create_member(target.pack_uid, library_kind=_RELIEF, local_uid="old",
                                               body=_relief_body("old"), world_uid="w1")
        plan = await self.plan([self.item(source.pack_uid)], selections=[self.select(target=target.pack_uid)])
        self.assertIsNone(plan.items[0].pack.value.source_pack_uid)
        self.assertTrue(all(w.value.member.creation_kind == "member_copy" for w in plan.items[0].members))
        self.assertEqual({w.value.member.source_template_uid for w in plan.items[0].members},
                         {r.template_uid for r in rows})
        self.assertEqual([r.template_uid for r in plan.removed], [old.template_uid])

    async def test_batch_removing_consumers_does_not_retain_their_references(self):
        structures = await self.service.create_pack(system_name="world.s", owner_world_uid="w1")
        plots = await self.service.create_pack(system_name="world.b", owner_world_uid="w1")
        row = await self.service.create_member(structures.pack_uid, library_kind=_STRUCT, local_uid="house",
                                               body={"display_name": "House"}, world_uid="w1")
        plot = await self.service.create_member(plots.pack_uid, library_kind=_PLOT, local_uid="plot",
                                                body=_plot_body("plot", row.template_uid), world_uid="w1")
        plan = await self.plan([self.item("s", key="s", imported=True), self.item("b", key="b", imported=True)],
            selections=[self.select(key="s", target=structures.pack_uid), self.select(key="b", target=plots.pack_uid)],
            imports={"s": WriteImportSource(structures, ()), "b": WriteImportSource(plots, ())})
        self.assertEqual({r.template_uid for r in plan.removed}, {row.template_uid, plot.template_uid})
        self.assertFalse(plan.held)

    async def test_batch_new_consumer_retains_removed_target(self):
        pack, structure, plot = await self.graph()
        raw = self.imported(name="world.new", local="newplot", kind=_PLOT,
                            body=_plot_body("newplot", structure.template_uid))
        plan = await self.plan([self.item("empty", key="e", imported=True), self.item("new", key="n", imported=True)],
            selections=[self.select(key="e", target=pack.pack_uid)],
            imports={"empty": WriteImportSource(pack, ()), "new": raw})
        self.assertEqual(set(dict(plan.held)), {structure.template_uid})
        self.assertEqual([r.template_uid for r in plan.removed], [plot.template_uid])
        self.assertFalse(plan.diagnostics)

    async def test_import_does_not_reject_existing_world_diagnostic(self):
        world = await self.worlds.get_by_id("w1")
        world.relief_pick_policy = {"open_land": {"default_template_uid": runtime_uid()}}
        await self.worlds.update(world)
        plan = await self.plan([self.item("raw", imported=True)], imports={"raw": self.imported()})
        self.assertTrue(plan.diagnostics)

    async def test_import_cannot_carry_uid_occupied_by_another_pack(self):
        pack, structure, _ = await self.graph()
        raw = self.imported(local="house", kind=_STRUCT, body={"display_name": "House"})
        raw = replace(raw, members=(WriteImportMember(replace(raw.members[0].member,
                                    template_uid=structure.template_uid), {"display_name": "House"}),))
        snapshot, decision = await self.ready([self.item("raw", imported=True)], imports={"raw": raw})
        with self.assertRaisesRegex(LibraryPackConflictError, "occupied"):
            self.planner.prepare(snapshot, decision)

    async def test_candidate_cycle_requires_a_root_in_projected_catalog(self):
        pack, structure, plot = await self.graph()
        adapter = self.service._scope.adapters[_STRUCT]
        # Future adapters may reference each other. A declared reverse edge
        # exercises the shared closure without adding fictitious domain fields.
        with patch.object(adapter, "body_refs", return_value=(
                MemberRef(_PLOT.value, plot.template_uid, structure.template_uid, "future_ref"),)):
            plan = await self.empty_replace(pack)
            self.assertEqual({r.template_uid for r in plan.removed}, {structure.template_uid, plot.template_uid})
            self.assertFalse(plan.held)
            world = await self.worlds.get_by_id("w1")
            world.library_pins = [{"library_kind": _STRUCT.value, "template_uid": structure.template_uid}]
            await self.worlds.update(world)
            plan = await self.empty_replace(pack)
            self.assertFalse(plan.removed)
            self.assertEqual(set(dict(plan.held)), {structure.template_uid, plot.template_uid})

    async def test_batch_pack_removal_and_member_replace_same_uid_rejected(self):
        pack, structure, plot = await self.graph()
        raw_member = WriteImportSource(pack, (WriteImportMember(structure, {"display_name": "Revision"}),))
        snapshot, decision = await self.ready([
            self.item("empty", key="e", imported=True),
            self.item("member", key="m", imported=True, target=pack.pack_uid, kind=_STRUCT)],
            selections=[self.select(key="e", target=pack.pack_uid), self.select(key="m", target=structure.template_uid)],
            imports={"empty": WriteImportSource(pack, ()), "member": raw_member})
        with self.assertRaisesRegex(LibraryPackConflictError, "excluded member"):
            self.planner.prepare(snapshot, decision)

