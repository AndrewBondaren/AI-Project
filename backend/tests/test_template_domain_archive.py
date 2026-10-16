"""A7 real SQLite/archive round trips of target-domain bodies and refs."""
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch

from tests.test_library_packs_4b import _ServiceCase
from tests.template_domain_transport_fixture import create_graph, S, B, P
from app.application.worldBundle.archive import read_archive
from app.application.worldBundle.worldLibraries import import_libraries
from app.application.templateLibrary.packs.archive.archiveSources import pack_to_wire
from app.application.templateLibrary.packs.errors import LibraryPackValidationError
from app.application.importResult import ImportResult
from app.application.templateLibrary.packs.legacy.legacyPack import legacy_pack_row
from app.ids import library_uid
from app.dataModel.worldBundle.libraryArchive import LibraryArchiveManifest, LibraryArchiveMember, LibraryArchivePack


class TemplateDomainArchiveTests(_ServiceCase):
    async def _world(self, world_uid):
        return await self.container.world_service().create({"world_uid": world_uid, "name": world_uid,
                                                           "created_at": "2026-10-14"})

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bundle = self.container.world_bundle_service()

    async def test_mixed_engine_archive_uses_uid_paths_for_all_kinds_and_keeps_duplicate_names(self):
        pack, _, structure, building, plot, duplicate = await create_graph(self)
        path = await self.service.archives.write_engine_archive(pack.pack_uid, path=Path(self.tmp.name) / "mixed.wpack")
        with ZipFile(path) as archive:
            paths = set(archive.namelist())
        for root, member in (("structures_templates", structure), ("building_templates", building),
                             ("building_templates", duplicate), ("plot_templates", plot)):
            self.assertIn(f"{root}/{pack.pack_uid}/{member.template_uid}.json", paths)
            self.assertIn(f"{root}/{pack.pack_uid}/pack.manifest.json", paths)
        decoded = read_archive(path).library_packs[0]
        self.assertEqual(len(decoded.manifest.members), 4)
        self.assertEqual({m.local_uid for m in decoded.manifest.members}, {"same"})
        self.assertEqual(decoded.bodies[plot.template_uid]["main_building"]["structure"], structure.template_uid)

    async def test_cross_pack_world_archive_copy_remaps_bodies_dependencies_and_pins(self):
        await self._world("source")
        pack, bodies_pack, structure, building, plot, duplicate = await create_graph(self, owner="source", separate=True)
        world = await self.worlds.get_by_id("source")
        world.library_pins = [{"library_kind": P.value, "template_uid": plot.template_uid},
                              {"library_kind": B.value, "template_uid": building.template_uid}]
        await self.worlds.update(world)
        original = await self.bundle.export("source")
        self.assertNotIn("plot_templates", original)
        self.assertNotIn("building_templates", original)
        path = self.bundle.write_archive(original, path=Path(self.tmp.name) / "world.wpack")
        results, rollback = await self.bundle.import_bundle(self.bundle.read_archive(path))
        self.assertFalse(rollback, results)
        copied = next(w for w in await self.worlds.get_all() if w.world_uid != "source")
        targets = {p.source_pack_uid: p for p in await self.packs.list_world_owned(copied.world_uid)}
        members = await self.members.list_by_packs([p.pack_uid for p in targets.values()])
        mapping = {m.source_template_uid: m.template_uid for m in members}
        self.assertEqual(len(mapping), 4)
        new_plot = await self.service.read_member_body(mapping[plot.template_uid])
        self.assertEqual(new_plot["main_building"]["structure"], mapping[structure.template_uid])
        self.assertEqual(new_plot["secondary_buildings"][0]["structure"], mapping[structure.template_uid])
        self.assertEqual((await self.service.read_member_body(mapping[building.template_uid]))["structure"], mapping[structure.template_uid])
        self.assertEqual(await self.deps.required_uids(targets[bodies_pack.pack_uid].pack_uid), {targets[pack.pack_uid].pack_uid})
        self.assertEqual({p["template_uid"] for p in copied.library_pins}, {mapping[plot.template_uid], mapping[building.template_uid]})
        self.assertFalse(await self.packs.list_engine())
        self.assertEqual(await self.bundle.export("source"), original)

    async def test_world_export_skips_empty_world_owned_pack(self):
        await self._world("source")
        pack, _, *_ = await create_graph(self, owner="source")
        empty = await self.service.create_pack(system_name="world.source.empty",
                                               owner_world_uid="source")
        bundle = await self.bundle.export("source")
        uids = {p["manifest"]["pack_uid"] for p in bundle["library_packs"]}
        self.assertIn(pack.pack_uid, uids)
        self.assertNotIn(empty.pack_uid, uids)
        # Single-pack export keeps the empty-pack guard.
        with self.assertRaises(LibraryPackValidationError):
            await self.service.archives.export_pack(empty.pack_uid)

    async def test_flat_legacy_plot_uses_converter_and_packed_structure_name_resolution(self):
        pack, _, structure, _, _, _ = await create_graph(self)
        wire = pack_to_wire(await self.service.archives.export_pack(pack.pack_uid))
        # Keep only structure in the transported source pack; plot is explicitly flat legacy input.
        wire["manifest"]["members"] = [m for m in wire["manifest"]["members"] if m["library_kind"] == S.value]
        wire["bodies"] = {structure.template_uid: wire["bodies"][structure.template_uid]}
        data = {"world": {"world_uid": "legacy", "name": "Legacy", "created_at": "2026-10-14"},
            "library_packs": [wire], "building_templates": [{"system_name": "plot", "display_name": "Edited",
                "main_building": {"structure": "same", "foundation_depth": 0},
                "secondary_buildings": [{"structure": structure.template_uid, "porch_has_roof": False}]}]}
        before = deepcopy(data)
        results, rollback = await self.bundle.import_bundle(data)
        self.assertFalse(rollback, results)
        target = next(w for w in await self.worlds.get_all())
        owned = await self.packs.list_world_owned(target.world_uid)
        members = await self.members.list_by_packs([p.pack_uid for p in owned])
        plot_member = next(m for m in members if m.library_kind == P)
        geometry = next(m for m in members if m.library_kind == S)
        body = await self.service.read_member_body(plot_member.template_uid)
        self.assertEqual(body["main_building"]["structure"], geometry.template_uid)
        self.assertEqual(body["main_building"]["foundation_depth"], 0)
        self.assertFalse(body["secondary_buildings"][0]["porch_has_roof"])
        self.assertFalse(any(m.library_kind == B for m in members))
        self.assertEqual(await self.deps.required_uids(plot_member.pack_uid), {geometry.pack_uid})
        self.assertEqual(data, before)

    async def test_validate_only_flat_outline_error_keeps_path_and_writes_nothing(self):
        data = {"world": {"world_uid": "legacy", "name": "Legacy", "created_at": "2026-10-14"},
                "building_templates": [{"system_name": "house", "display_name": "House"}]}
        trace = []
        await self.db.main_conn.set_trace_callback(trace.append)
        try:
            report = await self.bundle.import_bundle(data, validate_only=True)
        finally:
            await self.db.main_conn.set_trace_callback(None)
        self.assertFalse(report.valid)
        self.assertTrue(any(i.path == ("building_templates", 0, "structure") for i in report.issues))
        self.assertEqual(trace, [])
        self.assertFalse(await self.packs.list_all())

    async def test_modern_building_manifest_does_not_accept_legacy_plot_shape(self):
        pack, _, _, building, plot, _ = await create_graph(self)
        archive = await self.service.archives.export_pack(pack.pack_uid)
        invalid = replace_pack_body(archive, building.template_uid, archive.bodies[plot.template_uid])
        with self.assertRaises(LibraryPackValidationError):
            await self.service.archives.import_engine((invalid,))

    async def test_later_entity_failure_rolls_back_whole_mixed_graph(self):
        await self._world("source")
        await create_graph(self, owner="source")
        data = await self.bundle.export("source")
        handler = next(h for h in self.bundle._handlers if h.key == "states")
        data["states"] = []
        before = await self.packs.list_all()
        with patch.object(handler, "import_section", return_value=ImportResult(1, 0, 1)):
            _, rolled_back = await self.bundle.import_bundle(data)
        self.assertTrue(rolled_back)
        self.assertEqual(await self.packs.list_all(), before)
        self.assertEqual(len(await self.worlds.get_all()), 1)

    def test_flat_plot_composes_with_packed_structure_in_same_legacy_pack(self):
        pack = legacy_pack_row("legacy")
        uid = library_uid(S, "geometry", pack_uid=pack.pack_uid)
        archive = LibraryArchivePack(LibraryArchiveManifest(pack_uid=pack.pack_uid,
            system_name=pack.system_name, pack_name=pack.pack_name, display_name="Edited pack", version="2.0",
            members=[LibraryArchiveMember(library_kind=S, local_uid="geometry", template_uid=uid)]),
            {uid: {"system_name": uid, "display_name": "Edited geometry"}})
        data = {"world": {"world_uid": "legacy"}, "library_packs": [pack_to_wire(archive)],
            "plot_templates": [{"system_name": "plot", "display_name": "Plot", "main_building": {"structure": uid}}]}
        before = deepcopy(data)
        packs, consumed = import_libraries(data)
        self.assertEqual(len(packs), 1)
        self.assertEqual(len(packs[0].manifest.members), 2)
        self.assertEqual(packs[0].manifest.version, "2.0")
        self.assertEqual(packs[0].manifest.display_name, "Edited pack")
        self.assertEqual(packs[0].bodies[uid], archive.bodies[uid])
        self.assertEqual(consumed, {"plot_templates"})
        self.assertEqual(data, before)

    async def test_legacy_ambiguous_structure_name_reports_candidates_without_guessing(self):
        wires, candidates = [], []
        for name in ("user.left", "user.right"):
            pack = await self.service.create_pack(system_name=name)
            member = await self.service.create_member(pack.pack_uid, library_kind=S, local_uid="geometry",
                                                       body={"display_name": "Geometry"})
            candidates.append(member.template_uid)
            wires.append(pack_to_wire(await self.service.archives.export_pack(pack.pack_uid)))
        data = {"world": {"world_uid": "legacy", "name": "Legacy", "created_at": "2026-10-14"},
                "library_packs": wires, "building_templates": [{"system_name": "plot", "display_name": "Plot",
                    "main_building": {"structure": "geometry"}}]}
        report = await self.bundle.import_bundle(data, validate_only=True)
        self.assertFalse(report.valid)
        issue = next(i for i in report.issues if i.code == "LEGACY_REF_AMBIGUOUS")
        self.assertEqual(issue.path, ("building_templates", 0, "main_building.structure"))
        for uid in candidates:
            self.assertIn(uid, issue.message)
        self.assertFalse(await self.worlds.get_all())


def replace_pack_body(pack, uid, body):
    from dataclasses import replace
    return replace(pack, bodies={**pack.bodies, uid: body})
