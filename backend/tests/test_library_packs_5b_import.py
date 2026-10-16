"""5b/B2: legacy world migration applied through the shared writer inside the
world-import transaction; real SQLite, no fakes."""
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid5, NAMESPACE_DNS

from tests.test_library_packs_4b import _ServiceCase, _relief_body
from app.application.imports.result import ImportResult
from app.application.templateLibrary.packs.legacy.legacyPack import (
    legacy_member_uid,
    legacy_pack_uid,
)
from app.ids import LibraryKind

_R, _S, _P = (LibraryKind.RELIEF_TEMPLATES, LibraryKind.STRUCTURE_TEMPLATES,
              LibraryKind.PLOT_TEMPLATES)
_FORMER_OPEN_LAND = "21fb5cb8-eb9a-5f5d-a75b-e632135fc0b5"


class LegacyWorldImportTests(_ServiceCase):
    async def _world(self, world_uid):
        return await self.container.world_service().create(
            {"world_uid": world_uid, "name": world_uid, "created_at": "2026-10-10"})

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bundle = self.container.world_bundle_service()

    async def test_flat_legacy_bodies_become_world_legacy_members(self):
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10"},
                "relief_templates": [_relief_body("meadow"), _relief_body("shore")]}
        before = deepcopy(data)
        results, rolled = await self.bundle.import_bundle(data)
        self.assertFalse(rolled, results)
        target = next(w for w in await self.worlds.get_all())
        owned = await self.packs.list_world_owned(target.world_uid)
        self.assertEqual([p.pack_uid for p in owned], [legacy_pack_uid(target.world_uid)])
        members = await self.members.list_by_pack(owned[0].pack_uid)
        self.assertEqual({m.library_kind for m in members}, {_R.value})
        self.assertEqual({m.local_uid for m in members}, {"meadow", "shore"})
        for member in members:
            body = await self.service.read_member_body(member.template_uid)
            self.assertEqual(body["system_name"], member.local_uid)
        self.assertEqual(data, before)

    async def test_registry_pointers_and_pins_follow_composed_uid_map(self):
        source_member = legacy_member_uid(_R, "meadow", world_uid="src")
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10",
                "library_pins": [{"library_kind": _R.value, "template_uid": source_member}],
                "relief_template_registry": [{"system_template_uid": source_member,
                    "display_template_name": "Meadow", "context": "open_land",
                    "imported_at": "2026-10-10"}]},
                "relief_templates": [_relief_body("meadow")]}
        results, rolled = await self.bundle.import_bundle(data)
        self.assertFalse(rolled, results)
        target = next(w for w in await self.worlds.get_all())
        expected = legacy_member_uid(_R, "meadow", world_uid=target.world_uid)
        self.assertEqual([p["template_uid"] for p in target.library_pins], [expected])
        self.assertIsNotNone(await self.members.get_by_uid(expected))

    async def test_embedded_domain_graph_migrates_with_resolved_refs(self):
        structure_source = str(uuid5(NAMESPACE_DNS, "b2.mill"))
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10"},
                "structure_templates": [{"system_name": structure_source, "local_uid": "mill",
                                          "display_name": "Mill"}],
                "building_templates": [{"system_name": "plot", "display_name": "Plot",
                                        "main_building": {"structure": "mill"}}]}
        results, rolled = await self.bundle.import_bundle(data)
        self.assertFalse(rolled, results)
        target = next(w for w in await self.worlds.get_all())
        members = await self.members.list_by_pack(legacy_pack_uid(target.world_uid))
        by_kind = {m.library_kind: m for m in members}
        self.assertEqual(set(by_kind), {_S.value, _P.value})
        self.assertEqual(by_kind[_S.value].source_template_uid, structure_source)
        plot = await self.service.read_member_body(by_kind[_P.value].template_uid)
        self.assertEqual(plot["main_building"]["structure"], by_kind[_S.value].template_uid)

    async def test_relief_pick_policy_remaps_to_migrated_member(self):
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10",
                "relief_pick_policy": {"open_land": {"mode": "fixed",
                    "default_template_uid": _FORMER_OPEN_LAND}}},
                "relief_templates": [_relief_body("open_land_soft")]}
        results, rolled = await self.bundle.import_bundle(data)
        self.assertFalse(rolled, results)
        target = next(w for w in await self.worlds.get_all())
        expected = legacy_member_uid(_R, "open_land_soft", world_uid=target.world_uid)
        self.assertEqual(
            target.relief_pick_policy["open_land"]["default_template_uid"], expected)

    async def test_world_copy_composes_uid_maps_and_leaves_source(self):
        await self._world("src")
        pack = await self.service.create_pack(system_name="world.src.custom", owner_world_uid="src")
        member = await self.service.create_member(pack.pack_uid, library_kind=_R,
            local_uid="meadow", body=_relief_body("meadow"), world_uid="src")
        data = await self.bundle.export("src")
        before = await self.packs.list_all()
        results, rolled = await self.bundle.import_bundle(data)
        self.assertFalse(rolled, results)
        copied = next(w for w in await self.worlds.get_all() if w.world_uid != "src")
        owned = await self.packs.list_world_owned(copied.world_uid)
        instance = next(p for p in owned if p.source_pack_uid == pack.pack_uid)
        members = await self.members.list_by_pack(instance.pack_uid)
        self.assertEqual([m.source_template_uid for m in members],
                         [member.template_uid])
        # B6: no registry pointer was ever written for the source member,
        # so the copy migrates no pin — membership alone is availability.
        self.assertEqual(copied.library_pins or [], [])
        self.assertEqual(await self.packs.list_world_owned("src"),
                         [p for p in before if p.owner_world_uid == "src"])

    async def test_modern_archive_only_input_stays_on_archive_path(self):
        src = await self.service.create_pack(system_name="user.relief.set")
        member = await self.service.create_member(src.pack_uid, library_kind=_R,
            local_uid="meadow", body=_relief_body("meadow"))
        wire = (await self.service.archives.export_pack(src.pack_uid))
        from app.application.templateLibrary.packs.archive.archiveSources import pack_to_wire
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10"},
                "library_packs": [pack_to_wire(wire)]}
        results, rolled = await self.bundle.import_bundle(data)
        self.assertFalse(rolled, results)
        target = next(w for w in await self.worlds.get_all())
        owned = await self.packs.list_world_owned(target.world_uid)
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0].source_pack_uid, src.pack_uid)
        members = await self.members.list_by_pack(owned[0].pack_uid)
        self.assertEqual([m.source_template_uid for m in members], [member.template_uid])

    async def test_invalid_legacy_body_fails_with_issue_and_no_writes(self):
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10"},
                "relief_templates": [{"system_name": "broken"}]}
        with self.assertRaises(Exception):
            await self.bundle.import_bundle(data)
        self.assertEqual(await self.worlds.get_all(), [])
        self.assertEqual(await self.packs.list_all(), [])

    async def test_entity_failure_rolls_back_world_libraries_and_entities(self):
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10"},
                "relief_templates": [_relief_body("meadow")], "states": []}
        handler = next(h for h in self.bundle._handlers if h.key == "states")
        with patch.object(handler, "import_section", return_value=ImportResult(1, 0, 1)):
            _, rolled = await self.bundle.import_bundle(data)
        self.assertTrue(rolled)
        self.assertEqual(await self.worlds.get_all(), [])
        self.assertEqual(await self.packs.list_all(), [])
        self.assertEqual(await self.members.list_by_packs([]), [])

    async def test_repeated_import_has_deterministic_world_scoped_identities(self):
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10"},
                "relief_templates": [_relief_body("meadow")]}
        for _ in range(2):
            results, rolled = await self.bundle.import_bundle(data)
            self.assertFalse(rolled, results)
        worlds = await self.worlds.get_all()
        self.assertEqual(len(worlds), 2)
        for world in worlds:
            members = await self.members.list_by_pack(legacy_pack_uid(world.world_uid))
            self.assertEqual([m.template_uid for m in members],
                             [legacy_member_uid(_R, "meadow", world_uid=world.world_uid)])

    async def test_validate_only_reports_migration_issues_without_writes(self):
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10"},
                "structure_templates": [{"system_name": "not-a-uuid", "local_uid": "mill"}]}
        trace = []
        await self.db.main_conn.set_trace_callback(trace.append)
        try:
            report = await self.bundle.import_bundle(data, validate_only=True)
        finally:
            await self.db.main_conn.set_trace_callback(None)
        self.assertFalse(report.valid)
        self.assertTrue(any(i.code == "TEMPLATE_UID" for i in report.issues))
        self.assertEqual(trace, [])
        self.assertEqual(await self.packs.list_all(), [])

    async def test_imported_graph_resolves_independent_of_source(self):
        source_member = legacy_member_uid(_R, "meadow", world_uid="src")
        data = {"world": {"world_uid": "src", "name": "Src", "created_at": "2026-10-10",
                "library_pins": [{"library_kind": _R.value, "template_uid": source_member}]},
                "relief_templates": [_relief_body("meadow")]}
        results, rolled = await self.bundle.import_bundle(data)
        self.assertFalse(rolled, results)
        target = next(w for w in await self.worlds.get_all())
        pin = target.library_pins[0]
        self.assertEqual(pin["template_uid"],
                         legacy_member_uid(_R, "meadow", world_uid=target.world_uid))
        body = await self.service.read_member_body(pin["template_uid"])
        self.assertEqual(body["system_name"], "meadow")
