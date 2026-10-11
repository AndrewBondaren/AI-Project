"""L-2: real SQLite inspection, full matches, input state and no writes."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import AsyncMock

from test_library_packs_4b import _ServiceCase, _RELIEF, _STRUCT, _BUILDING, _plot_body, _relief_body
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.application.worldData.libraryPacks.defaults import STRUCTURES_BASE_SYSTEM_NAME
from app.application.worldData.libraryPacks.writeContracts import (
    LibraryWriteItem, LibraryWriteRequest, LibraryWriteSelection, WriteObjectKind,
    WritePolicy, WriteSource, WriteSourceKind, WriteStatus,
)
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteImportMember, WriteImportSource
from app.application.worldData.libraryPacks.writeInspector import LibraryWriteInspector
from app.application.worldData.libraryPacks.writePolicy import LibraryWritePolicy
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, library_uid, runtime_uid


class LibraryWriteInspectorTests(_ServiceCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self._world("w1")
        await self._world("w2")
        self.source_pack = await self.service.create_pack(system_name="world.w1.source", owner_world_uid="w1")
        self.target_pack = await self.service.create_pack(system_name="world.w1.target", owner_world_uid="w1")
        self.source_member = await self.service.create_member(
            self.source_pack.pack_uid, library_kind=_RELIEF, local_uid="meadow",
            body=_relief_body("meadow"), world_uid="w1")
        self.target_member = await self.service.create_member(
            self.target_pack.pack_uid, library_kind=_RELIEF, local_uid="meadow",
            body=_relief_body("meadow"), world_uid="w1")
        scope = self.service._scope
        self.inspector = LibraryWriteInspector(catalog=PackCatalogRepos(self.packs, self.members, self.deps),
                                               adapters=scope.adapters, worlds=scope.worlds)
        # Generation/inspection must never reach administrative list_all.
        self.packs.list_all = AsyncMock(side_effect=AssertionError("global bypass"))

    def member_request(self, *, target=None, source=None, owner="w1", decisions=(), token=None):
        item = LibraryWriteItem(item_key="entry", object_kind=WriteObjectKind.MEMBER,
                                source=source or WriteSource(kind=WriteSourceKind.CATALOG,
                                                            key=self.source_member.template_uid),
                                owner_world_uid=owner, target_pack_uid=target or self.target_pack.pack_uid,
                                library_kind=_RELIEF)
        return LibraryWriteRequest(items=(item,), decisions=decisions, preview_token=token)

    def pack_request(self, uid, *, owner="w1", decisions=(), token=None, imported=False):
        item = LibraryWriteItem(item_key="entry", object_kind=WriteObjectKind.PACK,
                                source=WriteSource(kind=WriteSourceKind.IMPORT if imported else WriteSourceKind.CATALOG,
                                                   key=uid), owner_world_uid=owner)
        return LibraryWriteRequest(items=(item,), decisions=decisions, preview_token=token)

    async def inspect(self, request, **kwargs):
        changes = self.db.main_conn.total_changes
        trace = []
        await self.db.main_conn.set_trace_callback(trace.append)
        try:
            result = await self.inspector.inspect(request, **kwargs)
        finally:
            await self.db.main_conn.set_trace_callback(None)
        self.assertEqual(self.db.main_conn.total_changes, changes)
        self.assertFalse([sql for sql in trace if sql.lstrip().split()[0].upper()
                          in {"INSERT", "UPDATE", "DELETE", "REPLACE", "BEGIN", "COMMIT"}])
        return result

    async def test_all_matches_sorted_and_legacy_accessor_stays_ambiguous(self):
        copy = await self.service.copy_member(self.target_member.template_uid,
                                               self.target_pack.pack_uid, world_uid="w1")
        rows = await self.members.list_by_local_uid(self.target_pack.pack_uid, _RELIEF.value, "meadow")
        self.assertEqual([m.template_uid for m in rows], sorted([self.target_member.template_uid, copy.member.template_uid]))
        with self.assertRaises(ValueError):
            await self.members.find_by_local_uid(self.target_pack.pack_uid, _RELIEF.value, "meadow")
        snap = await self.inspect(self.member_request())
        self.assertEqual([t.uid for t in snap.items[0].matches], [m.template_uid for m in rows])
        self.assertEqual(LibraryWritePolicy().decide(snap, self.member_request()).status, WriteStatus.POLICY_REQUIRED)

    async def test_same_key_in_other_pack_or_world_not_a_match(self):
        other = await self.service.create_pack(system_name="world.w2.target", owner_world_uid="w2")
        await self.service.create_member(other.pack_uid, library_kind=_RELIEF, local_uid="meadow",
                                         body=_relief_body("meadow"), world_uid="w2")
        snap = await self.inspect(self.member_request())
        self.assertEqual([t.uid for t in snap.items[0].matches], [self.target_member.template_uid])
        self.assertNotIn(other.pack_uid, {p.pack_uid for p in snap.inspection.scopes[0].packs})
        first = snap.preview_token
        await self.service.update_member_body((await self.members.list_by_pack(other.pack_uid))[0].template_uid,
                                               _relief_body("meadow", display_name="Other"), world_uid="w2")
        self.assertEqual(first, (await self.inspect(self.member_request())).preview_token)

    async def test_foreign_destination_is_fact_then_policy_rejects(self):
        foreign = await self.service.create_pack(system_name="world.w2.foreign", owner_world_uid="w2")
        request = self.member_request(target=foreign.pack_uid)
        snapshot = await self.inspect(request)
        self.assertEqual(snapshot.items[0].destination.owner_world_uid, "w2")
        self.assertEqual(LibraryWritePolicy().decide(snapshot, request).status, WriteStatus.REJECTED)

    async def test_missing_destination_and_source_are_not_executable(self):
        requests = (self.member_request(target=runtime_uid()),
                    self.member_request(source=WriteSource(kind="catalog", key=runtime_uid())),
                    self.member_request(owner="absent"))
        for request in requests:
            snapshot = await self.inspect(request)
            self.assertEqual(LibraryWritePolicy().decide(snapshot, request).status, WriteStatus.REJECTED)

    async def test_changed_source_body_and_target_body_stale_the_preview(self):
        request = self.member_request()
        initial = await self.inspect(request)
        for uid, pack in ((self.source_member.template_uid, self.source_pack),
                           (self.target_member.template_uid, self.target_pack)):
            await self.service.update_member_body(uid, _relief_body("meadow", display_name=pack.system_name), world_uid="w1")
            fresh = await self.inspect(request)
            self.assertNotEqual(initial.preview_token, fresh.preview_token)
            retry = request.model_copy(update={"decisions": (LibraryWriteSelection(item_key="entry", policy="copy"),),
                                               "preview_token": initial.preview_token})
            self.assertTrue(LibraryWritePolicy().decide(fresh, retry).stale)
            initial = fresh

    async def test_pins_and_provenance_invalidate_token(self):
        request = self.member_request()
        initial = await self.inspect(request)
        world = await self.worlds.get_by_id("w1")
        world.library_pins = [{"library_kind": _RELIEF.value, "template_uid": self.target_member.template_uid}]
        await self.worlds.update(world)
        pinned = await self.inspect(request)
        self.assertNotEqual(initial.preview_token, pinned.preview_token)
        self.assertIn(self.target_member.template_uid, dict(pinned.inspection.scopes[0].pins))
        copy = await self.service.copy_member(self.target_member.template_uid, self.target_pack.pack_uid, world_uid="w1")
        copied = await self.inspect(request)
        kept = next(m for m in copied.inspection.scopes[0].members if m.member.template_uid == copy.member.template_uid)
        self.assertEqual(kept.member.source_template_uid, self.target_member.template_uid)
        self.assertEqual(kept.member.creation_kind, "member_copy")
        self.assertNotEqual(pinned.preview_token, copied.preview_token)

    async def test_dependencies_include_transitive_edges_and_terminate_cycles(self):
        a = await self.service.create_pack(system_name="dependency.a")
        b = await self.service.create_pack(system_name="dependency.b")
        await self.service.set_dependencies(a.pack_uid, [b.pack_uid])
        await self.service.set_dependencies(b.pack_uid, [a.pack_uid])
        await self.service.set_dependencies(self.source_pack.pack_uid, [a.pack_uid], world_uid="w1")
        before = await self.inspect(self.member_request())
        graph = dict(before.inspection.dependency_edges)
        self.assertEqual(graph[a.pack_uid], (b.pack_uid,))
        self.assertEqual(graph[b.pack_uid], (a.pack_uid,))
        await self.service.set_dependencies(b.pack_uid, [])
        self.assertNotEqual(before.preview_token, (await self.inspect(self.member_request())).preview_token)

    async def test_refs_and_external_ownership_retained_without_global_body_load(self):
        external = await self.service.create_pack(system_name="engine.structures.external")
        structure = await self.service.create_member(external.pack_uid, library_kind=_STRUCT,
                                                     local_uid="house", body={"display_name": "House"})
        plot = await self.service.create_member(self.target_pack.pack_uid, library_kind=_BUILDING,
                                                local_uid="plot", body=_plot_body("plot", structure.template_uid), world_uid="w1")
        snapshot = await self.inspect(self.member_request())
        state = snapshot.inspection.scopes[0]
        self.assertTrue(any(r.consumer == plot.template_uid and r.template_uid == structure.template_uid for r in state.refs))
        self.assertIn(structure.template_uid, {m.template_uid for m in snapshot.inspection.known_members})
        self.assertNotIn(structure.template_uid, {m.member.template_uid for m in state.members})

    async def test_pack_instance_matching_and_new_copy_identity(self):
        source, _ = await self._relief_engine_pack()
        request = self.pack_request(source.pack_uid)
        self.assertFalse((await self.inspect(request)).items[0].matches)
        instance = await self.service.instantiate_pack(source.pack_uid, world_uid="w1")
        preview = await self.inspect(request)
        self.assertEqual([m.uid for m in preview.items[0].matches], [instance.pack.pack_uid])
        retry = request.model_copy(update={"decisions": (LibraryWriteSelection(
            item_key="entry", policy="copy", copy_system_name="new.independent.pack"),),
            "preview_token": preview.preview_token})
        fresh = await self.inspect(retry)
        self.assertEqual(preview.preview_token, fresh.preview_token)
        self.assertTrue(fresh.items[0].copy_identity_available)
        self.assertEqual(LibraryWritePolicy().decide(fresh, retry).status, WriteStatus.READY)
        await self.service.create_pack(system_name="new.independent.pack")
        occupied = await self.inspect(retry)
        self.assertFalse(occupied.items[0].copy_identity_available)
        self.assertEqual(LibraryWritePolicy().decide(occupied, retry).status, WriteStatus.REJECTED)

    async def test_publish_and_same_scope_pack_matches(self):
        same = await self.inspect(self.pack_request(self.source_pack.pack_uid))
        self.assertEqual([t.uid for t in same.items[0].matches], [self.source_pack.pack_uid])
        published = await self.service.copy_pack(self.source_pack.pack_uid)
        result = await self.inspect(self.pack_request(self.source_pack.pack_uid, owner=None))
        self.assertEqual([t.uid for t in result.items[0].matches], [published.pack.pack_uid])

    def imported(self, body=None):
        uid = library_uid(LibraryKind.LIBRARY_PACKS, "import.pack")
        pack = LibraryPackRow(uid, "import.pack", "pack", "Pack")
        member = LibraryPackMemberRow(library_uid(_RELIEF, "meadow", pack_uid=uid), uid, _RELIEF.value, "meadow")
        return WriteImportSource(pack, (WriteImportMember(member, body or _relief_body("meadow")),))

    async def test_parsed_import_is_validated_and_detached_before_apply(self):
        source = self.imported()
        original = deepcopy(source)
        request = self.member_request(source=WriteSource(kind="import", key="uploaded/entry"))
        snapshot = await self.inspect(request, imports={"uploaded/entry": source})
        self.assertEqual(source, original)
        retained = dict(snapshot.inspection.sources)["entry"].members[0]
        self.assertEqual(retained.outline.system_name, "meadow")
        source.members[0].body["display_name"] = "Changed after inspect"
        self.assertNotEqual(retained.body["display_name"], source.members[0].body["display_name"])
        self.assertIsNone(await self.packs.get_by_uid(source.pack.pack_uid))

    async def test_invalid_import_body_membership_and_missing_entry_rejected(self):
        request = self.member_request(source=WriteSource(kind="import", key="entry"))
        base = self.imported()
        bad_body = replace(base, members=(replace(base.members[0], body={"system_name": "wrong"}),))
        wrong_member = replace(base.members[0].member, pack_uid=runtime_uid())
        bad_owner = replace(base, members=(replace(base.members[0], member=wrong_member),))
        for imports in ({}, {"entry": bad_body}, {"entry": bad_owner}):
            snapshot = await self.inspect(request, imports=imports)
            self.assertTrue(snapshot.items[0].issues)
            self.assertEqual(LibraryWritePolicy().decide(snapshot, request).status, WriteStatus.REJECTED)

    async def test_batch_state_is_shared_but_sources_are_separate(self):
        first = self.member_request().items[0]
        second = first.model_copy(update={"item_key": "second"})
        request = LibraryWriteRequest(items=(first, second))
        snapshot = await self.inspect(request)
        self.assertEqual(len(snapshot.inspection.scopes), 1)
        self.assertEqual(len(snapshot.inspection.sources), 2)
        self.assertEqual(LibraryWritePolicy().decide(snapshot, request).actions, ())

    async def test_exact_uid_match_survives_changed_source_local_key(self):
        request = self.member_request(source=WriteSource(kind="import", key="entry"))
        member = replace(self.target_member, local_uid="changed")
        source = WriteImportSource(self.target_pack,
                                   (WriteImportMember(member, _relief_body("changed")),))
        result = await self.inspect(request, imports={"entry": source})
        self.assertEqual([m.uid for m in result.items[0].matches], [self.target_member.template_uid])

    async def test_missing_body_is_an_inspection_issue(self):
        await self.relief_rows.delete(self.source_member.template_uid)
        request = self.member_request()
        snapshot = await self.inspect(request)
        self.assertTrue(snapshot.items[0].issues)
        self.assertEqual(LibraryWritePolicy().decide(snapshot, request).status, WriteStatus.REJECTED)

    async def test_reserved_default_identity_requires_choice_even_before_attach(self):
        uid = library_uid(LibraryKind.LIBRARY_PACKS, STRUCTURES_BASE_SYSTEM_NAME)
        pack = LibraryPackRow(uid, STRUCTURES_BASE_SYSTEM_NAME, "base", "Base")
        source = WriteImportSource(pack, ())
        request = self.pack_request("entry", owner=None, imported=True)
        snapshot = await self.inspect(request, imports={"entry": source})
        self.assertEqual(snapshot.items[0].matches[0].uid, uid)
        self.assertTrue(snapshot.items[0].matches[0].is_default)
        self.assertEqual(LibraryWritePolicy().decide(snapshot, request).status, WriteStatus.POLICY_REQUIRED)
        self.assertIsNone(await self.packs.get_by_uid(uid))

    async def test_default_catalog_source_remains_canonical_not_implicit_world_instance(self):
        uid = library_uid(LibraryKind.LIBRARY_PACKS, STRUCTURES_BASE_SYSTEM_NAME)
        await self.packs.insert(LibraryPackRow(uid, STRUCTURES_BASE_SYSTEM_NAME, "base", "Base"))
        request = self.pack_request(uid)
        snapshot = await self.inspect(request)
        self.assertEqual([t.uid for t in snapshot.items[0].matches], [uid])
        decision = LibraryWritePolicy().decide(snapshot, request)
        self.assertEqual(decision.status, WriteStatus.POLICY_REQUIRED)
        self.assertTrue(decision.choices[0].options[0].allowed)
        self.assertFalse(decision.choices[0].options[1].allowed)

    async def test_invalid_creation_kind_and_duplicate_dependency_rejected(self):
        request = self.member_request(source=WriteSource(kind="import", key="entry"))
        base = self.imported()
        invalid_member = replace(base.members[0].member, creation_kind="unknown")
        dep = runtime_uid()
        for source in (replace(base, members=(replace(base.members[0], member=invalid_member),)),
                       replace(base, dependencies=(dep, dep))):
            snap = await self.inspect(request, imports={"entry": source})
            self.assertTrue(snap.items[0].issues)
            self.assertEqual(LibraryWritePolicy().decide(snap, request).status, WriteStatus.REJECTED)
