"""Library packs — plan library-packs-model.md step 4b.

Remap operations (TZ §1.1/§2/§4.1): ``instantiate_pack`` engine→world
snapshot with deterministic member remap + provenance, internal/external
body refs, world-side refs (registry pointers, pick-policy fields,
layout-embedded structure refs), ``local_uid`` collision policy,
re-instantiate identity; ``copy_pack`` publish world→engine with the
same remap and full source isolation.

Real SQLite, migrated schema — same fixture style as test_library_packs_4a.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.libraryPacks.errors import (
    LibraryPackConflictError,
    LibraryPackValidationError,
)
from app.application.worldData.loadReliefTemplatesForWorld import (
    load_relief_templates_for_world,
)
from app.core.container import Container
from app.db.database import Database
from app.db.models.world import World
from app.db.repositories.sqlite.buildingTemplateRepository import (
    SqliteBuildingTemplateRepository,
)
from app.db.repositories.sqlite.reliefTemplateRepository import (
    SqliteReliefTemplateRepository,
)
from app.db.repositories.sqlite.structureTemplateRepository import (
    SqliteStructureTemplateRepository,
)
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository
from app.ids import LibraryKind, library_uid

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STRUCTURES_ROOT = _REPO_ROOT / "structures_templates"
_BASE_SYSTEM_NAME = "engine.structures.base"

_STRUCT = LibraryKind.STRUCTURE_TEMPLATES
_RELIEF = LibraryKind.RELIEF_TEMPLATES
_BUILDING = LibraryKind.BUILDING_TEMPLATES
_PACKS = LibraryKind.LIBRARY_PACKS


def _relief_body(local_uid: str, **extra) -> dict:
    body = {
        "system_name": local_uid,
        "display_name": local_uid.title(),
        "context": "open_land",
    }
    body.update(extra)
    return body


def _plot_body(local_uid: str, structure_uid: str, **extra) -> dict:
    body = {
        "system_name": local_uid,
        "display_name": local_uid.title(),
        "plot_type": "dwelling",
        "main_building": {"structure": structure_uid},
    }
    body.update(extra)
    return body


class _ServiceCase(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(str(Path(self.tmp.name) / "test.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.service = self.container.library_pack_service()
        self.packs = self.container.library_pack_repository()
        self.members = self.container.library_pack_member_repository()
        self.deps = self.container.library_pack_dependency_repository()
        self.worlds = SqliteWorldRepository(self.db)
        self.relief_rows = SqliteReliefTemplateRepository(self.db)
        self.structure_rows = SqliteStructureTemplateRepository(self.db)
        self.building_rows = SqliteBuildingTemplateRepository(self.db)

    async def _world(self, world_uid: str) -> World:
        world = World(world_uid=world_uid, name=world_uid, created_at="2026-10-10")
        await self.worlds.create(world)
        return world

    async def _relief_engine_pack(self, system_name="user.relief.set", members=("meadow", "shore")):
        pack = await self.service.create_pack(system_name=system_name)
        rows = [
            await self.service.create_member(
                pack.pack_uid, library_kind=_RELIEF, local_uid=name,
                body=_relief_body(name),
            )
            for name in members
        ]
        return pack, rows


class InstantiateTests(_ServiceCase):

    async def test_instantiate_remaps_members_with_provenance(self):
        await self._world("w1")
        src, src_members = await self._relief_engine_pack()

        res = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        inst = res.pack
        self.assertTrue(res.created)
        self.assertEqual(inst.owner_world_uid, "w1")
        self.assertEqual(inst.source_pack_uid, src.pack_uid)
        self.assertEqual(
            inst.pack_uid,
            library_uid(_PACKS, f"world.w1.instance.{src.system_name}"),
        )
        self.assertEqual(inst.system_name, f"world.w1.instance.{src.system_name}")

        by_local = {m.local_uid: m for m in res.members}
        self.assertEqual(set(by_local), {"meadow", "shore"})
        for src_m in src_members:
            inst_m = by_local[src_m.local_uid]
            self.assertEqual(inst_m.pack_uid, inst.pack_uid)
            self.assertEqual(inst_m.source_template_uid, src_m.template_uid)
            self.assertEqual(
                inst_m.template_uid,
                library_uid(_RELIEF, src_m.local_uid, pack_uid=inst.pack_uid),
            )
            # Snapshot: a body row exists at the new uid and is the copy.
            inst_body = await self.service.read_member_body(inst_m.template_uid)
            src_body = await self.service.read_member_body(src_m.template_uid)
            self.assertIsNotNone(inst_body)
            self.assertEqual(inst_body["display_name"], src_body["display_name"])
            self.assertNotEqual(inst_m.template_uid, src_m.template_uid)

        # Source pack/members untouched.
        self.assertEqual(len(await self.members.list_by_pack(src.pack_uid)), 2)

    async def test_instantiate_pointer_targets_instance_not_source(self):
        await self._world("w1")
        src, _ = await self._relief_engine_pack()
        res = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")

        world = await self.worlds.get_by_id("w1")
        registry_uids = {
            e["system_template_uid"] for e in world.relief_template_registry
        }
        self.assertEqual(registry_uids, set(res.uid_map.values()))
        self.assertFalse(registry_uids & set(res.uid_map))

        # Registry readers resolve the world-owned copies.
        loaded = await load_relief_templates_for_world(
            self.container.relief_template_library_service(), world
        )
        self.assertEqual(set(loaded), set(res.uid_map.values()))

    async def test_instantiate_remaps_pick_policy_and_pointer(self):
        await self._world("w1")
        src, (m1, _m2) = await self._relief_engine_pack()
        src_uid = m1.template_uid
        # The world referenced the engine member before instantiation.
        await self.container.world_service().update("w1", {
            "relief_template_registry": [{
                "system_template_uid": src_uid,
                "display_template_name": "Meadow",
                "context": "open_land",
                "imported_at": "2026-10-10T00:00:00+00:00",
            }],
            "relief_pick_policy": {
                "open_land": {"mode": "fixed", "default_template_uid": src_uid},
                "shore": {"mode": "random"},
            },
        })

        res = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        new_uid = res.uid_map[src_uid]

        world = await self.worlds.get_by_id("w1")
        registry_uids = {
            e["system_template_uid"] for e in world.relief_template_registry
        }
        self.assertNotIn(src_uid, registry_uids)
        self.assertIn(new_uid, registry_uids)
        policy = world.relief_pick_policy
        self.assertEqual(
            policy["open_land"]["default_template_uid"], new_uid
        )
        self.assertEqual(policy["shore"]["mode"], "random")
        self.assertIsNone(policy["shore"]["default_template_uid"])

    async def test_instantiate_structure_pack_remaps_embedded_layout_refs(self):
        await self._world("w1")
        src = await self.service.create_pack(system_name="user.structures.s")
        sm = await self.service.create_member(
            src.pack_uid, library_kind=_STRUCT, local_uid="barn",
            body={"display_name": "Barn"},
        )
        foreign = "3fa85f64-5717-4562-b3fc-2c963f66afa6"  # not in the pack
        # World-authored plot layouts embed structure refs (world-side
        # refs). Plot rows are storage-legal but fail the registry-entry
        # POJO, so they land via the repository — like prepare_import.
        world = await self.worlds.get_by_id("w1")
        world.building_template_registry = [
            {
                "system_name": "p1",
                "display_name": "P1",
                "main_building": {"structure": sm.template_uid},
                "secondary_buildings": [{"structure": sm.template_uid}],
            },
            {
                "system_name": "p2",
                "display_name": "P2",
                "main_building": {"structure": foreign},
            },
        ]
        await self.worlds.update(world)

        res = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        new_uid = res.uid_map[sm.template_uid]

        world = await self.worlds.get_by_id("w1")
        p1, p2 = world.building_template_registry
        self.assertEqual(p1["main_building"]["structure"], new_uid)
        self.assertEqual(p1["secondary_buildings"][0]["structure"], new_uid)
        # Refs that never pointed at source members stay (TZ §2).
        self.assertEqual(p2["main_building"]["structure"], foreign)

        # Model A: the copied body embeds the new member uid.
        body = await self.structure_rows.get_by_uid(new_uid)
        self.assertIsNotNone(body)
        self.assertEqual(body.data["system_name"], new_uid)
        # Source body unchanged.
        src_body = await self.structure_rows.get_by_uid(sm.template_uid)
        self.assertEqual(src_body.data["system_name"], sm.template_uid)

    async def test_internal_refs_remapped_external_untouched(self):
        await self._world("w1")
        # Multi-kind pack: the plot's structure ref targets a member of
        # the SAME pack → internal ref, remapped (TZ §2).
        src = await self.service.create_pack(system_name="user.mixed")
        sm = await self.service.create_member(
            src.pack_uid, library_kind=_STRUCT, local_uid="barn",
            body={"display_name": "Barn"},
        )
        other = await self.service.create_pack(system_name="user.structures.other")
        om = await self.service.create_member(
            other.pack_uid, library_kind=_STRUCT, local_uid="silo",
            body={"display_name": "Silo"},
        )
        bm = await self.service.create_member(
            src.pack_uid, library_kind=_BUILDING, local_uid="farm_plot",
            body=_plot_body(
                "farm_plot",
                sm.template_uid,
                secondary_buildings=[{"structure": om.template_uid}],
            ),
        )

        res = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        new_body = await self.service.read_member_body(res.uid_map[bm.template_uid])
        self.assertEqual(
            new_body["main_building"]["structure"],
            res.uid_map[sm.template_uid],
        )
        # External ref (another pack's member) stays untouched.
        self.assertEqual(
            new_body["secondary_buildings"][0]["structure"], om.template_uid
        )

    async def test_reinstantiate_returns_same_instance(self):
        await self._world("w1")
        src, _ = await self._relief_engine_pack()
        first = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        second = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(second.pack.pack_uid, first.pack.pack_uid)
        self.assertEqual(
            {m.template_uid for m in second.members},
            {m.template_uid for m in first.members},
        )
        self.assertEqual(
            len(await self.members.list_by_pack(first.pack.pack_uid)), 2
        )

    async def test_reinstantiate_after_delete_is_deterministic(self):
        await self._world("w1")
        src, _ = await self._relief_engine_pack()
        first = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        await self.service.delete_pack(first.pack.pack_uid, world_uid="w1")
        second = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        self.assertTrue(second.created)
        self.assertEqual(second.pack.pack_uid, first.pack.pack_uid)
        self.assertEqual(
            {m.template_uid for m in second.members},
            {m.template_uid for m in first.members},
        )

    async def test_local_uid_collision_rejected(self):
        await self._world("w1")
        world_pack = await self.service.create_pack(
            system_name="world.w1.relief", owner_world_uid="w1"
        )
        await self.service.create_member(
            world_pack.pack_uid, library_kind=_RELIEF, local_uid="meadow",
            body=_relief_body("meadow"), world_uid="w1",
        )
        engine, _ = await self._relief_engine_pack(members=("meadow",))
        with self.assertRaises(LibraryPackConflictError):
            await self.service.instantiate_pack(engine.pack_uid, world_uid="w1")
        self.assertIsNone(
            await self.packs.find_instance("w1", engine.pack_uid)
        )
        # A different domain with the same local key is not a collision.
        engine2 = await self.service.create_pack(system_name="user.buildings.b")
        await self.service.create_member(
            engine2.pack_uid, library_kind=_BUILDING, local_uid="meadow",
            body={
                "system_name": "meadow",
                "display_name": "Meadow B",
                "structure_types": ["farm"],
            },
        )
        res = await self.service.instantiate_pack(engine2.pack_uid, world_uid="w1")
        self.assertTrue(res.created)

    async def test_instantiate_gates(self):
        await self._world("w1")
        # World-owned packs never instantiate (TZ §1.1).
        world_pack = await self.service.create_pack(
            system_name="world.w1.relief", owner_world_uid="w1"
        )
        with self.assertRaises(LibraryPackValidationError):
            await self.service.instantiate_pack(world_pack.pack_uid, world_uid="w2")
        # Nonexistent world.
        engine, _ = await self._relief_engine_pack(members=("a",))
        with self.assertRaises(LibraryPackValidationError):
            await self.service.instantiate_pack(engine.pack_uid, world_uid="ghost")
        # Declared default — already available, instance would detach from
        # canonical attach (TZ §6).
        await self.service.import_fs_pack(
            _STRUCT, _STRUCTURES_ROOT / "base", domain_root=_STRUCTURES_ROOT
        )
        base_uid = library_uid(_PACKS, _BASE_SYSTEM_NAME)
        with self.assertRaises(LibraryPackValidationError):
            await self.service.instantiate_pack(base_uid, world_uid="w1")

    async def test_dependencies_copied_never_instantiated(self):
        await self._world("w1")
        dep = await self.service.create_pack(system_name="user.dep")
        src, _ = await self._relief_engine_pack(
            system_name="user.main", members=("meadow",)
        )
        await self.service.set_dependencies(src.pack_uid, [dep.pack_uid])

        res = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        inst_deps = await self.deps.required_uids(res.pack.pack_uid)
        self.assertEqual(inst_deps, {dep.pack_uid})
        # The dependency pack itself is not instantiated (TZ §1/§5).
        self.assertIsNone(await self.packs.find_instance("w1", dep.pack_uid))
        self.assertEqual(res.missing_dependencies, ())

        # Missing dependency: diagnosed, never auto-instantiated.
        ghost = library_uid(_PACKS, "user.ghost")
        src2, _ = await self._relief_engine_pack(
            system_name="user.miss", members=("x",)
        )
        await self.service.set_dependencies(src2.pack_uid, [ghost])
        res2 = await self.service.instantiate_pack(src2.pack_uid, world_uid="w1")
        self.assertEqual(res2.missing_dependencies, (ghost,))

    async def test_snapshot_isolation(self):
        await self._world("w1")
        src, (m1, _m2) = await self._relief_engine_pack()
        res = await self.service.instantiate_pack(src.pack_uid, world_uid="w1")
        inst_uid = res.uid_map[m1.template_uid]

        # Editing the engine source never reaches the instance.
        await self.service.update_member_body(
            m1.template_uid, _relief_body("meadow", display_name="Engine v2")
        )
        inst_body = await self.service.read_member_body(inst_uid)
        self.assertEqual(inst_body["display_name"], "Meadow")

        # Editing the instance never reaches the source.
        await self.service.update_member_body(
            inst_uid, _relief_body("meadow", display_name="World v2"),
            world_uid="w1",
        )
        src_body = await self.service.read_member_body(m1.template_uid)
        self.assertEqual(src_body["display_name"], "Engine v2")


class PublishTests(_ServiceCase):

    async def _world_pack_with_member(self, world_uid="w1"):
        await self._world(world_uid)
        pack = await self.service.create_pack(
            system_name=f"world.{world_uid}.relief", owner_world_uid=world_uid
        )
        member = await self.service.create_member(
            pack.pack_uid, library_kind=_RELIEF, local_uid="meadow",
            body=_relief_body("meadow"), world_uid=world_uid,
        )
        return pack, member

    async def test_copy_pack_publishes_to_engine(self):
        wpack, wmember = await self._world_pack_with_member()
        res = await self.service.copy_pack(wpack.pack_uid)
        pub = res.pack
        self.assertTrue(res.created)
        self.assertIsNone(pub.owner_world_uid)
        self.assertEqual(pub.source_pack_uid, wpack.pack_uid)
        self.assertEqual(pub.system_name, f"{wpack.system_name}.published")

        (new_member,) = res.members
        self.assertEqual(new_member.source_template_uid, wmember.template_uid)
        self.assertEqual(
            new_member.template_uid,
            library_uid(_RELIEF, "meadow", pack_uid=pub.pack_uid),
        )
        self.assertIsNotNone(
            await self.relief_rows.get_by_uid(new_member.template_uid)
        )
        self.assertIn(pub.pack_uid, {p.pack_uid for p in await self.service.list_engine_packs()})

        # The source world pack and its pointers are untouched.
        world = await self.worlds.get_by_id("w1")
        self.assertEqual(
            {e["system_template_uid"] for e in world.relief_template_registry},
            {wmember.template_uid},
        )
        self.assertEqual(
            len(await self.members.list_by_pack(wpack.pack_uid)), 1
        )

    async def test_copy_pack_custom_system_name(self):
        wpack, _ = await self._world_pack_with_member()
        res = await self.service.copy_pack(
            wpack.pack_uid, system_name="user.relief.myset"
        )
        self.assertEqual(res.pack.system_name, "user.relief.myset")
        # Re-publish to the same identity collides — publish is explicit.
        with self.assertRaises(LibraryPackConflictError):
            await self.service.copy_pack(
                wpack.pack_uid, system_name="user.relief.myset"
            )

    async def test_copy_pack_snapshot_isolation(self):
        wpack, wmember = await self._world_pack_with_member()
        res = await self.service.copy_pack(wpack.pack_uid)
        (pub_member,) = res.members

        # Editing the published copy never reaches the world member.
        await self.service.update_member_body(
            pub_member.template_uid, _relief_body("meadow", display_name="Pub v2")
        )
        world_body = await self.service.read_member_body(wmember.template_uid)
        self.assertEqual(world_body["display_name"], "Meadow")

        # Editing the world member never reaches the published copy.
        await self.service.update_member_body(
            wmember.template_uid, _relief_body("meadow", display_name="World v2"),
            world_uid="w1",
        )
        pub_body = await self.service.read_member_body(pub_member.template_uid)
        self.assertEqual(pub_body["display_name"], "Pub v2")

    async def test_copy_pack_requires_world_source(self):
        engine, _ = await self._relief_engine_pack(members=("meadow",))
        with self.assertRaises(LibraryPackValidationError):
            await self.service.copy_pack(engine.pack_uid)


if __name__ == "__main__":
    unittest.main()
