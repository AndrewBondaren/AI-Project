"""A4: target domain bodies through the real common SQLite writer."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from test_library_packs_4b import _ServiceCase, _plot_body
import test_library_write_plan as plan_fixture
from app.application.worldData.libraryPacks.writeContracts import LibraryWriteRequest
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteImportSource
from app.application.worldData.libraryPacks.writeResults import PolicyRequired, WriteRejected, WriteResult
from app.application.worldData.libraryPacks.errors import LibraryPackPolicyRequiredError
from app.dataModel.locations.structure.building.buildingTemplate import BuildingTemplate
from app.dataModel.locations.structure.building.plotTemplate import PlotTemplate
from app.ids import LibraryKind, runtime_uid

S, B, P = (LibraryKind.STRUCTURE_TEMPLATES, LibraryKind.BUILDING_TEMPLATES,
           LibraryKind.PLOT_TEMPLATES)


class TemplateDomainWriterTests(_ServiceCase):
    item = plan_fixture.LibraryWritePlanTests.item
    select = plan_fixture.LibraryWritePlanTests.select
    imported = plan_fixture.LibraryWritePlanTests.imported

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self._world("w1")
        self.writer = self.container.library_write_service()
        self.plot_rows = self.container.plot_template_repository()

    async def graph(self, name="engine.graph", owner=None):
        pack = await self.service.create_pack(system_name=name, owner_world_uid=owner)
        structure = await self.service.create_member(pack.pack_uid, library_kind=S,
            local_uid="shared", body={"display_name": "Structure"}, world_uid=owner)
        building = await self.service.create_member(pack.pack_uid, library_kind=B,
            local_uid="shared", body={"system_name": "shared", "display_name": "Building",
                "structure": structure.template_uid, "porch_has_roof": False}, world_uid=owner)
        plot = await self.service.create_member(pack.pack_uid, library_kind=P,
            local_uid="shared", body=_plot_body("shared", structure.template_uid,
                secondary_buildings=[{"structure": structure.template_uid}]), world_uid=owner)
        return pack, structure, building, plot

    async def traced(self, request, imports=None):
        trace = []
        await self.db.main_conn.set_trace_callback(trace.append)
        try:
            result = await self.writer.execute(request, imports=imports)
        finally:
            await self.db.main_conn.set_trace_callback(None)
        self.assertFalse(any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                             for sql in trace), trace)
        return result

    async def test_mixed_pack_instance_remaps_all_structure_refs_and_keeps_source(self):
        pack, structure, building, plot = await self.graph()
        before = {m.template_uid: await self.service.read_member_body(m.template_uid)
                  for m in (structure, building, plot)}
        instance = await self.service.instantiate_pack(pack.pack_uid, world_uid="w1")
        mapping = {m.source_template_uid: m.template_uid for m in instance.members}
        self.assertEqual(len(set(mapping.values())), 3)
        copied_building = await self.building_rows.get_by_uid(mapping[building.template_uid])
        copied_plot = await self.plot_rows.get_by_uid(mapping[plot.template_uid])
        self.assertIsNone(copied_building.structure_type)
        self.assertEqual(copied_building.data["structure"], mapping[structure.template_uid])
        self.assertEqual(copied_plot.data["main_building"]["structure"], mapping[structure.template_uid])
        self.assertEqual(copied_plot.data["secondary_buildings"][0]["structure"], mapping[structure.template_uid])
        self.assertEqual(copied_building.data["foundation_type"], "slab")
        self.assertIsNone(copied_building.data["foundation_material"])
        self.assertFalse(copied_building.data["porch_has_roof"])
        self.assertEqual((await self.structure_rows.get_by_uid(mapping[structure.template_uid])).data[
            "system_name"], mapping[structure.template_uid])
        for uid, raw in before.items():
            self.assertEqual(await self.service.read_member_body(uid), raw)
        self.assertFalse((await self.worlds.get_by_id("w1")).building_template_registry)

    async def test_modern_building_rejects_legacy_plot_and_outline_without_writes(self):
        pack = await self.service.create_pack(system_name="world.strict", owner_world_uid="w1")
        for body in (_plot_body("old", runtime_uid()),
                     {"system_name": "old", "display_name": "Old", "structure_type": "dwelling"}):
            raw = self.imported(kind=B, local="old", body=body)
            request = LibraryWriteRequest(items=(self.item("raw", imported=True,
                target=pack.pack_uid, kind=B),))
            result = await self.traced(request, {"raw": raw})
            self.assertIsInstance(result, WriteRejected)
        self.assertFalse(await self.members.list_by_pack(pack.pack_uid))

    async def test_policy_and_stale_preview_do_not_write_modern_bodies(self):
        pack, _, building, _ = await self.graph(owner="w1")
        body = await self.service.read_member_body(building.template_uid)
        raw = self.imported(kind=B, local="shared", body={**body, "display_name": "Revision"})
        request = LibraryWriteRequest(items=(self.item("raw", imported=True,
            target=pack.pack_uid, kind=B),))
        preview = await self.traced(request, {"raw": raw})
        self.assertIsInstance(preview, PolicyRequired)
        selected = request.model_copy(update={"decisions": (self.select(target=building.template_uid),),
                                             "preview_token": preview.preview_token})
        changed = replace(raw, members=(replace(raw.members[0],
            body={**body, "display_name": "Changed again"}),))
        stale = await self.traced(selected, {"raw": changed})
        self.assertIsInstance(stale, PolicyRequired)
        self.assertTrue(stale.stale)
        result = await self.writer.execute(selected, imports={"raw": raw})
        self.assertIsInstance(result, WriteResult)
        self.assertEqual(await self.members.get_by_uid(building.template_uid), building)
        self.assertEqual((await self.building_rows.get_by_uid(building.template_uid)).display_name, "Revision")

    async def test_failure_in_mixed_copy_rolls_back_pack_members_bodies_and_world(self):
        pack, *_ = await self.graph()
        world_before = deepcopy(await self.worlds.get_by_id("w1"))
        adapter = self.container.pack_domain_adapters()[P]
        with patch.object(adapter, "persist_prepared", side_effect=ValueError("plot write failed")):
            with self.assertRaisesRegex(ValueError, "plot write failed"):
                await self.service.instantiate_pack(pack.pack_uid, world_uid="w1")
        self.assertFalse(await self.packs.list_world_owned("w1"))
        for kind, repo in ((P, self.plot_rows), (B, self.building_rows), (S, self.structure_rows)):
            self.assertEqual(len(await repo.list_all()), 1)
        self.assertEqual(await self.worlds.get_by_id("w1"), world_before)

    async def test_pins_retain_building_plot_and_transitive_structure_on_replace(self):
        pack, structure, building, plot = await self.graph(owner="w1")
        world = await self.worlds.get_by_id("w1")
        world.library_pins = [{"library_kind": kind.value, "template_uid": member.template_uid}
                              for kind, member in ((B, building), (P, plot))]
        await self.worlds.update(world)
        request = LibraryWriteRequest(items=(self.item("empty", imported=True),))
        imports = {"empty": WriteImportSource(pack, ())}
        preview = await self.writer.execute(request, imports=imports)
        result = await self.writer.execute(request.model_copy(update={
            "decisions": (self.select(target=pack.pack_uid),), "preview_token": preview.preview_token}),
            imports=imports)
        self.assertIsInstance(result, WriteResult)
        self.assertEqual({m.template_uid for m in await self.members.list_by_pack(pack.pack_uid)},
                         {m.template_uid for m in (structure, building, plot)})

    async def test_public_domain_writes_use_same_writer_and_require_caller_uow_for_storage(self):
        pack, structure, building, plot = await self.graph(owner="w1")
        for service, model, member in ((self.container.plot_template_library_service(), PlotTemplate, plot),
                                      (self.container.building_template_library_service(), BuildingTemplate, building)):
            body = model.model_validate(await self.service.read_member_body(member.template_uid))
            revised = body.model_copy(update={"display_name": "Edited"})
            with self.assertRaises(LibraryPackPolicyRequiredError):
                await service.write_body(revised, pack_uid=pack.pack_uid,
                    template_uid=member.template_uid, world_uid="w1")
            fresh = revised.model_copy(update={"system_name": "new"})
            row = await service.write_body(fresh, pack_uid=pack.pack_uid, world_uid="w1")
            self.assertEqual(row.display_name, "Edited")
            with self.assertRaisesRegex(RuntimeError, "caller UOW"):
                await service.persist_prepared(body, template_uid=member.template_uid,
                    source_file=None, added=False)

    async def test_same_name_member_copies_remain_distinct_and_preserve_structure_ref(self):
        pack, structure, building, plot = await self.graph(owner="w1")
        for member in (building, plot):
            copied = await self.service.copy_member(member.template_uid, pack.pack_uid, world_uid="w1")
            self.assertNotEqual(copied.member.template_uid, member.template_uid)
            self.assertEqual(copied.member.local_uid, member.local_uid)
            self.assertEqual(copied.member.source_template_uid, member.template_uid)
            body = await self.service.read_member_body(copied.member.template_uid)
            ref = body["structure"] if member == building else body["main_building"]["structure"]
            self.assertEqual(ref, structure.template_uid)
        self.assertEqual(len(await self.members.list_by_pack(pack.pack_uid)), 5)
