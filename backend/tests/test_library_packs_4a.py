"""Library packs — plan library-packs-model.md step 4a.

``LibraryPackService``: pack/member CRUD with ownership enforcement
(TZ §0.2/§1.1/§3), FS pack import into engine libraries, and the
transitional dual-write of world registry pointers (world-owned member
uid, never an engine member) — registries stay the availability SoT
until step 5b.

Real SQLite, migrated schema — same fixture style as test_library_packs_b3.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.libraryPacks.errors import (
    LibraryPackConflictError,
    LibraryPackInUseError,
    LibraryPackNotFoundError,
    LibraryPackOwnershipError,
    LibraryPackReadOnlyError,
    LibraryPackValidationError,
)
from app.application.worldData.libraryPacks.uidMap import pin_for_member
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
_BASE_PACK_UID = library_uid(LibraryKind.LIBRARY_PACKS, _BASE_SYSTEM_NAME)

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
        world = World(world_uid=world_uid, name=world_uid, created_at="2026-10-09")
        await self.worlds.create(world)
        return world


class PackCrudTests(_ServiceCase):

    async def test_engine_pack_lifecycle(self):
        pack = await self.service.create_pack(
            system_name="user.relief.extra",
            display_name="Extra relief",
        )
        self.assertIsNone(pack.owner_world_uid)
        self.assertEqual(pack.pack_uid, library_uid(_PACKS, "user.relief.extra"))
        self.assertEqual(pack.pack_name, "extra")
        self.assertIn(pack.pack_uid, {p.pack_uid for p in await self.service.list_engine_packs()})
        self.assertIn(pack.pack_uid, {p.pack_uid for p in await self.service.list_packs()})

        same = await self.service.get_pack(pack.pack_uid)
        self.assertEqual(same.system_name, "user.relief.extra")

        updated = await self.service.update_pack_metadata(
            pack.pack_uid, display_name="Extra v2", version="2.0"
        )
        self.assertEqual(updated.display_name, "Extra v2")
        self.assertEqual(updated.system_name, "user.relief.extra")
        self.assertIsNone(updated.owner_world_uid)

        result = await self.service.delete_pack(pack.pack_uid)
        self.assertEqual(result.members_removed, 0)
        self.assertIsNone(await self.service.find_pack(pack.pack_uid))
        with self.assertRaises(LibraryPackNotFoundError):
            await self.service.get_pack(pack.pack_uid)

    async def test_duplicate_system_name_rejected(self):
        await self.service.create_pack(system_name="user.dup")
        with self.assertRaises(LibraryPackConflictError):
            await self.service.create_pack(system_name="user.dup")

    async def test_invalid_owner_world_rejected_atomically(self):
        with self.assertRaises(LibraryPackValidationError):
            await self.service.create_pack(
                system_name="user.ghost", owner_world_uid="no-such-world"
            )
        self.assertIsNone(
            await self.service.find_pack(library_uid(_PACKS, "user.ghost"))
        )

    async def test_world_owned_pack_lifecycle(self):
        await self._world("w1")
        pack = await self.service.create_pack(
            system_name="world.w1.custom", owner_world_uid="w1"
        )
        self.assertEqual(pack.owner_world_uid, "w1")
        self.assertIn(pack.pack_uid, {p.pack_uid for p in await self.service.list_world_packs("w1")})
        self.assertNotIn(pack.pack_uid, {p.pack_uid for p in await self.service.list_engine_packs()})

        # Caller scope must match the owner world (TZ §1.1).
        with self.assertRaises(LibraryPackOwnershipError):
            await self.service.update_pack_metadata(
                pack.pack_uid, display_name="hijack", world_uid="w2"
            )
        with self.assertRaises(LibraryPackOwnershipError):
            await self.service.delete_pack(pack.pack_uid, world_uid="w2")
        await self.service.delete_pack(pack.pack_uid, world_uid="w1")
        self.assertIsNone(await self.service.find_pack(pack.pack_uid))

    async def test_default_identity_reserved(self):
        with self.assertRaises(LibraryPackReadOnlyError):
            await self.service.create_pack(system_name=_BASE_SYSTEM_NAME)

    async def test_missing_dependencies_diagnosed_not_blocked(self):
        pack = await self.service.create_pack(
            system_name="user.needs.base",
            dependencies=[library_uid(_PACKS, "not.imported.yet")],
        )
        self.assertEqual(
            await self.service.missing_dependencies(pack.pack_uid),
            {library_uid(_PACKS, "not.imported.yet")},
        )
        # Self-dependency and uid-safety rejected up front.
        with self.assertRaises(LibraryPackValidationError):
            await self.service.create_pack(
                system_name="user.selfdep", dependencies=[
                    library_uid(_PACKS, "user.selfdep")
                ],
            )
        with self.assertRaises(LibraryPackValidationError):
            await self.service.set_dependencies(pack.pack_uid, ["bad|uid"])


class MemberCrudTests(_ServiceCase):

    async def _engine_pack(self, system_name="user.relief.extra"):
        return await self.service.create_pack(system_name=system_name)

    async def test_relief_member_crud(self):
        pack = await self._engine_pack()
        member = await self.service.create_member(
            pack.pack_uid,
            library_kind=_RELIEF,
            local_uid="meadow",
            body=_relief_body("meadow"),
        )
        expected_uid = library_uid(_RELIEF, "meadow", pack_uid=pack.pack_uid)
        self.assertEqual(member.template_uid, expected_uid)
        self.assertEqual(member.local_uid, "meadow")
        self.assertIsNotNone(await self.relief_rows.get_by_uid(expected_uid))
        self.assertEqual(
            (await self.service.read_member_body(expected_uid))["display_name"],
            "Meadow",
        )

        await self.service.update_member_body(
            expected_uid, _relief_body("meadow", display_name="Meadow v2")
        )
        self.assertEqual(
            (await self.relief_rows.get_by_uid(expected_uid)).display_name,
            "Meadow v2",
        )

        members = await self.service.list_members(pack.pack_uid)
        self.assertEqual([m.template_uid for m in members], [expected_uid])

        result = await self.service.delete_member(expected_uid)
        self.assertEqual(result.template_uid, expected_uid)
        self.assertIsNone(await self.members.get_by_uid(expected_uid))
        self.assertIsNone(await self.relief_rows.get_by_uid(expected_uid))

    async def test_local_uid_unique_per_pack(self):
        pack = await self._engine_pack()
        await self.service.create_member(
            pack.pack_uid, library_kind=_RELIEF, local_uid="dup",
            body=_relief_body("dup"),
        )
        with self.assertRaises(LibraryPackConflictError):
            await self.service.create_member(
                pack.pack_uid, library_kind=_RELIEF, local_uid="dup",
                body=_relief_body("dup"),
            )
        # Same local key in another pack is a different member.
        other = await self._engine_pack("user.relief.other")
        second = await self.service.create_member(
            other.pack_uid, library_kind=_RELIEF, local_uid="dup",
            body=_relief_body("dup"),
        )
        self.assertNotEqual(second.pack_uid, pack.pack_uid)

    async def test_invalid_body_rolls_back(self):
        pack = await self._engine_pack()
        uid = library_uid(_RELIEF, "broken", pack_uid=pack.pack_uid)
        with self.assertRaises(LibraryPackValidationError):
            await self.service.create_member(
                pack.pack_uid, library_kind=_RELIEF, local_uid="broken",
                body={"system_name": "broken"},  # no display_name/context
            )
        self.assertIsNone(await self.members.get_by_uid(uid))
        self.assertIsNone(await self.relief_rows.get_by_uid(uid))

    async def test_body_identity_must_match_member(self):
        pack = await self._engine_pack()
        with self.assertRaises(LibraryPackValidationError):
            await self.service.create_member(
                pack.pack_uid, library_kind=_RELIEF, local_uid="declared",
                body=_relief_body("different"),
            )
        uid = library_uid(_RELIEF, "declared", pack_uid=pack.pack_uid)
        self.assertIsNone(await self.relief_rows.get_by_uid(uid))
        self.assertIsNone(await self.members.get_by_uid(uid))

    async def test_member_into_missing_pack_rejected(self):
        with self.assertRaises(LibraryPackNotFoundError):
            await self.service.create_member(
                "missing-pack", library_kind=_RELIEF, local_uid="x",
                body=_relief_body("x"),
            )

    async def test_unknown_kind_rejected(self):
        pack = await self._engine_pack()
        with self.assertRaises(LibraryPackValidationError):
            await self.service.create_member(
                pack.pack_uid, library_kind="no_such_kind",
                local_uid="x", body={},
            )
        with self.assertRaises(LibraryPackValidationError):
            await self.service.create_member(
                pack.pack_uid, library_kind=_PACKS,
                local_uid="x", body={},
            )

    async def test_structure_member_model_a(self):
        """Structures carry the member uid inside the body (model A)."""
        pack = await self.service.create_pack(system_name="user.structures.s")
        member = await self.service.create_member(
            pack.pack_uid, library_kind=_STRUCT, local_uid="house",
            body={"display_name": "House"},
        )
        expected_uid = library_uid(_STRUCT, "house", pack_uid=pack.pack_uid)
        self.assertEqual(member.template_uid, expected_uid)
        row = await self.structure_rows.get_by_uid(expected_uid)
        self.assertIsNotNone(row)
        self.assertEqual(row.data["system_name"], expected_uid)

        # A body carrying a foreign uid is rejected — no partial write.
        with self.assertRaises(LibraryPackValidationError):
            await self.service.create_member(
                pack.pack_uid, library_kind=_STRUCT, local_uid="shop",
                body={"system_name": "not-the-member-uid", "display_name": "Shop"},
            )
        self.assertIsNone(
            await self.structure_rows.get_by_uid(
                library_uid(_STRUCT, "shop", pack_uid=pack.pack_uid)
            )
        )

    async def test_building_member_crud(self):
        pack = await self.service.create_pack(system_name="user.buildings.b")
        member = await self.service.create_member(
            pack.pack_uid, library_kind=_BUILDING, local_uid="mill_x",
            body={
                "system_name": "mill_x",
                "display_name": "Mill",
                "structure_types": ["farm"],
            },
        )
        uid = library_uid(_BUILDING, "mill_x", pack_uid=pack.pack_uid)
        self.assertEqual(member.template_uid, uid)
        self.assertIsNotNone(await self.building_rows.get_by_uid(uid))


class DefaultPackTests(_ServiceCase):
    """Declared defaults are read-only (TZ §6) — no member writes."""

    async def _import_base(self):
        return await self.service.import_fs_pack(
            _STRUCT, _STRUCTURES_ROOT / "base", domain_root=_STRUCTURES_ROOT
        )

    async def test_fs_import_creates_engine_library(self):
        result = await self._import_base()
        self.assertEqual(result.pack.pack_uid, _BASE_PACK_UID)
        self.assertIsNone(result.pack.owner_world_uid)
        self.assertEqual(len(result.bodies), 13)
        self.assertEqual(len(result.missing_dependencies), 0)
        members = await self.members.list_by_pack(_BASE_PACK_UID)
        self.assertEqual(len(members), 13)

    async def test_default_pack_rejects_member_writes(self):
        await self._import_base()
        with self.assertRaises(LibraryPackReadOnlyError):
            await self.service.create_member(
                _BASE_PACK_UID, library_kind=_STRUCT, local_uid="forge",
                body={"display_name": "Forge"},
            )
        member = (await self.members.list_by_pack(_BASE_PACK_UID))[0]
        with self.assertRaises(LibraryPackReadOnlyError):
            await self.service.update_member_body(
                member.template_uid, {"display_name": "X"}
            )
        with self.assertRaises(LibraryPackReadOnlyError):
            await self.service.delete_member(member.template_uid)
        with self.assertRaises(LibraryPackReadOnlyError):
            await self.service.update_pack_metadata(
                _BASE_PACK_UID, display_name="fork"
            )
        with self.assertRaises(LibraryPackReadOnlyError):
            await self.service.delete_pack(_BASE_PACK_UID)
        # Untouched.
        self.assertEqual(len(await self.members.list_by_pack(_BASE_PACK_UID)), 13)

    async def test_building_kind_has_no_fs_root(self):
        with self.assertRaises(LibraryPackValidationError):
            await self.service.import_fs_pack(_BUILDING, Path("anywhere"))


class OwnershipAndDualWriteTests(_ServiceCase):
    """World-owned packs: owner-scope gate + registry-pointer dual-write."""

    async def test_world_member_visible_to_registry_readers(self):
        await self._world("w1")
        pack = await self.service.create_pack(
            system_name="world.w1.relief", owner_world_uid="w1"
        )
        member = await self.service.create_member(
            pack.pack_uid, library_kind=_RELIEF, local_uid="meadow",
            body=_relief_body("meadow"), world_uid="w1",
        )
        # Dual-write: pointer targets the world-owned member uid.
        world = await self.worlds.get_by_id("w1")
        self.assertIn(
            member.template_uid,
            {e["system_template_uid"] for e in world.relief_template_registry},
        )
        loaded = await load_relief_templates_for_world(
            self.container.relief_template_library_service(), world
        )
        self.assertIn(member.template_uid, loaded)
        self.assertEqual(loaded[member.template_uid].system_name, "meadow")

        # Member delete drops the pointer in the same operation.
        await self.service.delete_member(member.template_uid, world_uid="w1")
        world = await self.worlds.get_by_id("w1")
        self.assertEqual(
            [e for e in world.relief_template_registry
             if e["system_template_uid"] == member.template_uid],
            [],
        )
        self.assertIsNone(await self.relief_rows.get_by_uid(member.template_uid))

    async def test_world_member_requires_owner_scope(self):
        await self._world("w1")
        pack = await self.service.create_pack(
            system_name="world.w1.relief", owner_world_uid="w1"
        )
        with self.assertRaises(LibraryPackOwnershipError):
            await self.service.create_member(
                pack.pack_uid, library_kind=_RELIEF, local_uid="x",
                body=_relief_body("x"),
            )
        with self.assertRaises(LibraryPackOwnershipError):
            await self.service.create_member(
                pack.pack_uid, library_kind=_RELIEF, local_uid="x",
                body=_relief_body("x"), world_uid="w2",
            )

    async def test_building_member_pointer_dual_write(self):
        await self._world("w2")
        pack = await self.service.create_pack(
            system_name="world.w2.buildings", owner_world_uid="w2"
        )
        member = await self.service.create_member(
            pack.pack_uid, library_kind=_BUILDING, local_uid="mill_x",
            body={
                "system_name": "mill_x",
                "display_name": "Mill",
                "structure_types": ["farm"],
            },
            world_uid="w2",
        )
        world = await self.worlds.get_by_id("w2")
        self.assertIn(
            member.template_uid,
            {e["system_template_uid"] for e in world.building_template_registry},
        )

    async def test_pinned_member_delete_refused(self):
        await self._world("w3")
        pack = await self.service.create_pack(
            system_name="world.w3.relief", owner_world_uid="w3"
        )
        member = await self.service.create_member(
            pack.pack_uid, library_kind=_RELIEF, local_uid="meadow",
            body=_relief_body("meadow"), world_uid="w3",
        )
        await self.container.world_service().update(
            "w3", {"library_pins": [pin_for_member(_RELIEF, "meadow")]}
        )
        with self.assertRaises(LibraryPackInUseError) as ctx:
            await self.service.delete_member(member.template_uid, world_uid="w3")
        self.assertTrue(ctx.exception.usages)
        self.assertIsNotNone(await self.members.get_by_uid(member.template_uid))

        # Explicit override deletes, but reports the dangling reference.
        result = await self.service.delete_member(
            member.template_uid, allow_used=True, world_uid="w3"
        )
        self.assertTrue(result.diagnostics)
        self.assertIsNone(await self.members.get_by_uid(member.template_uid))


class DeletePackSafetyTests(_ServiceCase):

    async def test_delete_engine_pack_does_not_break_worlds(self):
        """Worlds hold instance copies — engine source delete is safe (TZ §1.1)."""
        await self._world("w1")
        engine = await self.service.create_pack(system_name="user.relief.shared")
        engine_member = await self.service.create_member(
            engine.pack_uid, library_kind=_RELIEF, local_uid="meadow",
            body=_relief_body("meadow"),
        )
        # The world's copy: own pack, own member, own pointer.
        world_pack = await self.service.create_pack(
            system_name="world.w1.shared", owner_world_uid="w1",
        )
        world_member = await self.service.create_member(
            world_pack.pack_uid, library_kind=_RELIEF, local_uid="meadow",
            body=_relief_body("meadow"), world_uid="w1",
        )
        self.assertNotEqual(engine_member.template_uid, world_member.template_uid)

        await self.service.delete_pack(engine.pack_uid)
        self.assertIsNone(await self.members.get_by_uid(engine_member.template_uid))

        world = await self.worlds.get_by_id("w1")
        loaded = await load_relief_templates_for_world(
            self.container.relief_template_library_service(), world
        )
        self.assertIn(world_member.template_uid, loaded)

    async def test_dependent_pack_delete_requires_force(self):
        base = await self.service.create_pack(system_name="user.base")
        child = await self.service.create_pack(
            system_name="user.child", dependencies=[base.pack_uid]
        )
        with self.assertRaises(LibraryPackInUseError) as ctx:
            await self.service.delete_pack(base.pack_uid)
        self.assertIn(child.pack_uid, ctx.exception.usages)
        self.assertIsNotNone(await self.service.find_pack(base.pack_uid))

        result = await self.service.delete_pack(base.pack_uid, force=True)
        self.assertTrue(result.diagnostics)
        self.assertIsNone(await self.service.find_pack(base.pack_uid))
        # The dependent's declaration survives as diagnosable dangling ref.
        self.assertEqual(
            await self.service.missing_dependencies(child.pack_uid),
            {base.pack_uid},
        )

    async def test_delete_world_pack_drops_pointers(self):
        await self._world("w4")
        pack = await self.service.create_pack(
            system_name="world.w4.relief", owner_world_uid="w4"
        )
        member = await self.service.create_member(
            pack.pack_uid, library_kind=_RELIEF, local_uid="meadow",
            body=_relief_body("meadow"), world_uid="w4",
        )
        result = await self.service.delete_pack(pack.pack_uid, world_uid="w4")
        self.assertEqual(result.members_removed, 1)
        world = await self.worlds.get_by_id("w4")
        self.assertEqual(world.relief_template_registry, [])
        self.assertIsNone(await self.relief_rows.get_by_uid(member.template_uid))


if __name__ == "__main__":
    unittest.main()
