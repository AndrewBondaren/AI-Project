"""L-4 application boundary: real SQLite, outer rollback and no-write negotiation."""
import asyncio
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import test_library_write_plan as plan_fixture
import test_library_packs_b3 as fs_fixture
from test_library_packs_4b import _ServiceCase
from app.application.worldData.libraryPacks.writeInspector import LibraryWriteInspector
from app.application.worldData.libraryPacks.writePlanner import LibraryWritePlanner
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.application.worldData.libraryPacks.writeContracts import LibraryWriteRequest, LibraryWriteSelection, WriteAction
from app.application.worldData.libraryPacks.writeResults import PolicyRequired, WriteResult, WriteRejected
from app.application.worldData.libraryPacks.errors import LibraryPackConflictError, LibraryPackPolicyRequiredError, LibraryPackReadOnlyError
from app.db.models.reliefTemplate import ReliefTemplateRow
from app.ids import LibraryKind
from app.db.database import Database


class LibraryWriteServiceTests(_ServiceCase):
    item = plan_fixture.LibraryWritePlanTests.item
    imported = plan_fixture.LibraryWritePlanTests.imported
    select = plan_fixture.LibraryWritePlanTests.select
    ready = plan_fixture.LibraryWritePlanTests.ready

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self._world("w1")
        scope = self.service._scope
        self.inspector = LibraryWriteInspector(catalog=PackCatalogRepos(self.packs, self.members, self.deps),
                                               adapters=scope.adapters, worlds=scope.worlds)
        self.planner = LibraryWritePlanner(scope.adapters)
        self.writer = self.container.library_write_service()

    def request(self, *items):
        return LibraryWriteRequest(items=items)

    async def apply_selection(self, request, preview, *selections, imports=None):
        return await self.writer.execute(request.model_copy(update={
            "decisions": selections, "preview_token": preview.preview_token}), imports=imports)

    async def test_no_match_applies_prepared_member_and_world(self):
        raw = self.imported()
        result = await self.writer.execute(self.request(self.item("raw", imported=True)), imports={"raw": raw})
        self.assertIsInstance(result, WriteResult)
        self.assertEqual(await self.packs.get_by_uid(raw.pack.pack_uid), raw.pack)
        self.assertEqual((await self.relief_rows.get_by_uid(raw.members[0].member.template_uid)).display_name, "Meadow")
        world = await self.worlds.get_by_id("w1")
        # B6: membership replaces the registry pointer write.
        self.assertEqual(world.relief_template_registry or [], [])
        self.assertEqual(
            [m.template_uid for m in await self.members.list_for_world("w1")],
            [raw.members[0].member.template_uid],
        )

    async def test_collision_preview_contains_diff_and_does_not_write(self):
        raw = self.imported()
        request = self.request(self.item("raw", imported=True))
        await self.writer.execute(request, imports={"raw": raw})
        revised = replace(raw, members=(replace(raw.members[0], body={**raw.members[0].body, "display_name": "Revised"}),))
        trace = []
        await self.db.main_conn.set_trace_callback(trace.append)
        try:
            preview = await self.writer.execute(request, imports={"raw": revised})
        finally:
            await self.db.main_conn.set_trace_callback(None)
        self.assertIsInstance(preview, PolicyRequired)
        self.assertTrue(any(p.plan and p.plan.items[0].members[0].changes for p in preview.preview))
        self.assertFalse(any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in trace))
        result = await self.apply_selection(request, preview, self.select(target=raw.pack.pack_uid), imports={"raw": revised})
        self.assertIsInstance(result, WriteResult)

    async def test_stale_import_body_and_target_return_preview_without_apply(self):
        raw = self.imported()
        request = self.request(self.item("raw", imported=True))
        await self.writer.execute(request, imports={"raw": raw})
        preview = await self.writer.execute(request, imports={"raw": raw})
        revised = replace(raw, members=(replace(raw.members[0], body={**raw.members[0].body, "display_name": "Changed"}),))
        stale = await self.apply_selection(request, preview, self.select(target=raw.pack.pack_uid), imports={"raw": revised})
        self.assertIsInstance(stale, PolicyRequired)
        self.assertTrue(stale.stale)
        self.assertEqual((await self.relief_rows.get_by_uid(raw.members[0].member.template_uid)).display_name, "Meadow")

    async def test_outer_uow_rolls_back_entities_and_libraries_without_nested_begin(self):
        raw = self.imported()
        trace = []
        await self.db.main_conn.set_trace_callback(trace.append)
        try:
            with self.assertRaisesRegex(ValueError, "entity failed"):
                async with self.db.transaction():
                    result = await self.writer.execute(self.request(self.item("raw", imported=True)), imports={"raw": raw})
                    self.assertIsInstance(result, WriteResult)
                    world = await self.worlds.get_by_id("w1")
                    world.name = "entity changed"
                    await self.worlds.update(world)
                    raise ValueError("entity failed")
        finally:
            await self.db.main_conn.set_trace_callback(None)
        self.assertIsNone(await self.packs.get_by_uid(raw.pack.pack_uid))
        self.assertEqual((await self.worlds.get_by_id("w1")).name, "w1")
        self.assertEqual(sum(sql.startswith("BEGIN") for sql in trace), 1)
        self.assertFalse(any(sql.startswith("COMMIT") for sql in trace))

    async def test_second_body_failure_rolls_back_complete_batch(self):
        left, right = self.imported("batch.left"), self.imported("batch.right")
        adapter = self.service._scope.adapters[self.item("x", target="x", kind="relief_templates").library_kind]
        original = adapter.persist_prepared
        calls = 0
        async def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("body failed")
            return await original(*args, **kwargs)
        with patch.object(adapter, "persist_prepared", side_effect=fail_second):
            with self.assertRaisesRegex(ValueError, "body failed"):
                await self.writer.execute(self.request(self.item("left", key="a", imported=True),
                    self.item("right", key="b", imported=True)), imports={"left": left, "right": right})
        self.assertIsNone(await self.packs.get_by_uid(left.pack.pack_uid))
        self.assertIsNone(await self.relief_rows.get_by_uid(left.members[0].member.template_uid))

    async def test_body_without_membership_cannot_be_silently_overwritten(self):
        raw = self.imported()
        uid = raw.members[0].member.template_uid
        await self.relief_rows.insert(ReliefTemplateRow(uid, "occupied", "Occupied", "open_land"))
        with self.assertRaises(LibraryPackConflictError):
            await self.writer.execute(self.request(self.item("raw", imported=True)), imports={"raw": raw})
        self.assertEqual((await self.relief_rows.get_by_uid(uid)).display_name, "Occupied")
        self.assertIsNone(await self.packs.get_by_uid(raw.pack.pack_uid))

    async def test_incomplete_batch_selection_does_not_write_unmatched_item(self):
        raw, fresh = self.imported(), self.imported("batch.fresh")
        await self.writer.execute(self.request(self.item("raw", imported=True)), imports={"raw": raw})
        result = await self.writer.execute(self.request(self.item("raw", key="a", imported=True),
            self.item("fresh", key="b", imported=True)), imports={"raw": raw, "fresh": fresh})
        self.assertIsInstance(result, PolicyRequired)
        self.assertIsNone(await self.packs.get_by_uid(fresh.pack.pack_uid))

    async def test_executor_refuses_outside_uow(self):
        raw = self.imported()
        snapshot, decision = await self.ready([self.item("raw", imported=True)], imports={"raw": raw})
        with self.assertRaisesRegex(RuntimeError, "caller"):
            await self.writer._executor.apply(self.planner.prepare(snapshot, decision))

    async def test_competing_tasks_create_once_then_negotiate(self):
        raw = self.imported()
        request = self.request(self.item("raw", imported=True))
        results = await asyncio.gather(*(self.writer.execute(request, imports={"raw": raw}) for _ in range(2)))
        self.assertEqual(sum(isinstance(r, WriteResult) for r in results), 1)
        self.assertEqual(sum(isinstance(r, PolicyRequired) for r in results), 1)

    async def test_bootstrap_uow_cannot_authorize_main_connection(self):
        raw = self.imported()
        async with self.db.transaction_on(self.db.bootstrap_conn):
            with self.assertRaisesRegex(RuntimeError, "main connection"):
                await self.writer.execute(self.request(self.item("raw", imported=True)), imports={"raw": raw})
        self.assertIsNone(await self.packs.get_by_uid(raw.pack.pack_uid))

    def fs_pack(self, *, count=1):
        root = Path(self.tmp.name) / "relief_templates"
        uid = fs_fixture.library_uid(LibraryKind.LIBRARY_PACKS, "test.pack.user")
        members = [fs_fixture._member_dict("user", kind=LibraryKind.RELIEF_TEMPLATES,
            pack_uid=uid, local_uid=f"body_{i}") for i in range(count)]
        manifest = fs_fixture._manifest_dict("user", kind=LibraryKind.RELIEF_TEMPLATES, members=members)
        path = fs_fixture._write_pack(root, "user", manifest=manifest,
            bodies={m["local_uid"]: {"system_name": m["local_uid"], "display_name": "Original", "context": "open_land"}
                    for m in members})
        return root, path, manifest

    async def test_fs_rereads_source_and_returns_stale_without_writing(self):
        root, path, manifest = self.fs_pack()
        await self.service.import_fs_pack(LibraryKind.RELIEF_TEMPLATES, path, domain_root=root)
        preview = await self.service.import_fs_pack(LibraryKind.RELIEF_TEMPLATES, path, domain_root=root)
        body_path = path / "body_0.json"
        body = json.loads(body_path.read_text(encoding="utf-8"))
        body["display_name"] = "Revised"
        body_path.write_text(json.dumps(body), encoding="utf-8")
        stale = await self.service.import_fs_pack(LibraryKind.RELIEF_TEMPLATES, path, domain_root=root,
            decisions=(LibraryWriteSelection(item_key="fs", policy="replace", target_uid=manifest["pack_uid"]),),
            preview_token=preview.preview_token)
        self.assertIsInstance(stale, PolicyRequired)
        self.assertTrue(stale.stale)
        self.assertEqual((await self.relief_rows.get_by_uid(manifest["members"][0]["template_uid"])).display_name, "Original")

    async def test_fs_single_member_replace_preserves_other_members(self):
        root, path, manifest = self.fs_pack(count=2)
        await self.service.import_fs_pack(LibraryKind.RELIEF_TEMPLATES, path, domain_root=root)
        body_path = path / "body_0.json"
        preview = await self.service.import_fs_pack(LibraryKind.RELIEF_TEMPLATES, body_path, domain_root=root)
        uid = manifest["members"][0]["template_uid"]
        applied = await self.service.import_fs_pack(LibraryKind.RELIEF_TEMPLATES, body_path, domain_root=root,
            decisions=(LibraryWriteSelection(item_key="fs", policy="replace", target_uid=uid),),
            preview_token=preview.preview_token)
        self.assertEqual(len(applied.bodies), 1)
        self.assertEqual(len(await self.members.list_by_pack(manifest["pack_uid"])), 2)

    async def test_canonical_repeat_preserves_body_and_direct_delete_is_blocked(self):
        root = Path(__file__).resolve().parents[2] / "structures_templates"
        result = await self.service.import_fs_pack(LibraryKind.STRUCTURE_TEMPLATES, root / "base", domain_root=root)
        row = result.bodies[0]
        row.display_name = "Existing override"
        row.data["display_name"] = row.display_name
        await self.structure_rows.save(row)
        await self.service.import_fs_pack(LibraryKind.STRUCTURE_TEMPLATES, root / "base", domain_root=root)
        self.assertEqual((await self.structure_rows.get_by_uid(row.template_uid)).display_name, "Existing override")
        with self.assertRaises(LibraryPackReadOnlyError):
            await self.container.structure_template_library_service().delete(row.template_uid)

    async def test_domain_upsert_duplicate_requires_policy_and_leaves_body(self):
        pack, (member,) = await self._relief_engine_pack(members=("meadow",))
        with self.assertRaises(LibraryPackPolicyRequiredError) as caught:
            await self.container.relief_template_library_service().upsert_from_dict(
                {"system_name": "meadow", "display_name": "Overwrite", "context": "open_land"},
                pack_uid=pack.pack_uid)
        self.assertIsInstance(caught.exception.outcome, PolicyRequired)
        self.assertEqual((await self.relief_rows.get_by_uid(member.template_uid)).display_name, "Meadow")

    async def test_copy_preview_describes_consequences_without_allocating_uid(self):
        raw = self.imported()
        request = self.request(self.item("raw", imported=True))
        await self.writer.execute(request, imports={"raw": raw})
        with patch("app.application.worldData.libraryPacks.memberWritePlanner.runtime_uid", side_effect=AssertionError("allocated")):
            preview = await self.writer.execute(request, imports={"raw": raw})
        copy = next(p.copy for p in preview.preview if p.copy)
        self.assertTrue(copy.remaps_internal_references)
        self.assertTrue(copy.requires_pack_system_name)
        self.assertTrue(copy.source_unchanged)
        self.assertFalse(copy.replaces_existing)

    async def test_canonical_validation_failure_leaves_no_catalog_or_bodies(self):
        root = Path(__file__).resolve().parents[2] / "structures_templates"
        adapter = self.service._scope.adapter_for(LibraryKind.STRUCTURE_TEMPLATES)
        original, count = adapter.prepare_body, 0
        def fail_second(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise ValueError("invalid second canonical body")
            return original(*args, **kwargs)
        with patch.object(adapter, "prepare_body", side_effect=fail_second):
            with self.assertRaisesRegex(ValueError, "second canonical"):
                await self.service.import_fs_pack(LibraryKind.STRUCTURE_TEMPLATES, root / "base", domain_root=root)
        self.assertEqual(await self.structure_rows.list_all(), [])
        self.assertEqual(await self.packs.list_all(), [])

    async def test_another_connection_change_invalidates_previous_preview(self):
        raw = self.imported()
        request = self.request(self.item("raw", imported=True))
        await self.writer.execute(request, imports={"raw": raw})
        preview = await self.writer.execute(request, imports={"raw": raw})
        other = Database(self.db.path)
        await other.connect()
        try:
            async with other.transaction():
                await other.main_conn.execute("UPDATE library_packs SET version=? WHERE pack_uid=?", ("2.0", raw.pack.pack_uid))
        finally:
            await other.disconnect()
        stale = await self.apply_selection(request, preview, self.select(target=raw.pack.pack_uid), imports={"raw": raw})
        self.assertIsInstance(stale, PolicyRequired)
        self.assertTrue(stale.stale)
        self.assertEqual((await self.packs.get_by_uid(raw.pack.pack_uid)).version, "2.0")

    async def test_copy_only_match_does_not_hide_other_replace_preview(self):
        from app.application.worldData.libraryPacks.fsWriteSource import read_fs_write_source
        root = Path(__file__).resolve().parents[2] / "structures_templates"
        await self.service.import_fs_pack(LibraryKind.STRUCTURE_TEMPLATES, root / "base", domain_root=root)
        default = read_fs_write_source(LibraryKind.STRUCTURE_TEMPLATES, root / "base", domain_root=root).source
        raw = self.imported(owner=None)
        await self.writer.execute(self.request(self.item("raw", owner=None, imported=True)), imports={"raw": raw})
        preview = await self.writer.execute(self.request(self.item("default", key="default", owner=None, imported=True),
            self.item("raw", key="raw", owner=None, imported=True)), imports={"default": default, "raw": raw})
        self.assertIsInstance(preview, PolicyRequired)
        self.assertTrue(any(p.plan and any(a.item_key == "raw" and a.action is WriteAction.REPLACE
            for a in p.actions) for p in preview.preview))
