"""A2 storage/identity contracts on the real initial schema in a temporary DB."""

from dataclasses import replace
import sqlite3
import tempfile
import unittest

from app.core.container import Container
from app.dataModel.locations.structure.building import PlotTemplate
from app.db.database import Database
from app.db.mapper import model_columns
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.plotTemplate import PlotTemplateRow
from app.db.repositories.sqlite.libraryPackMemberRepository import SqliteLibraryPackMemberRepository
from app.db.repositories.sqlite.libraryPackRepository import SqliteLibraryPackRepository
from app.db.repositories.sqlite.plotTemplateRepository import SqlitePlotTemplateRepository
from app.ids import LibraryKind, library_uid, remapped_library_uid, runtime_uid


_PLOTS = LibraryKind.PLOT_TEMPLATES
_STRUCTURE = "00000000-0000-4000-8000-000000000013"


def pack(key):
    return LibraryPackRow(library_uid(LibraryKind.LIBRARY_PACKS, key), key, key, key)


def row(uid, **overrides):
    body = PlotTemplate.model_validate({
        "system_name": "shared", "display_name": "Plot",
        "main_building": {"structure": _STRUCTURE, "foundation_depth": 0},
        "secondary_buildings": [{"structure": _STRUCTURE, "porch_has_roof": True}],
    })
    return PlotTemplateRow(uid, body.system_name, body.display_name,
                           body.model_dump(mode="json"), **overrides)


class PlotStorageTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(self.temp.name + "/templates.db")
        await self.db.connect()
        await self.db.apply_migrations()
        self.repo = SqlitePlotTemplateRepository(self.db)
        self.packs = SqliteLibraryPackRepository(self.db)
        self.members = SqliteLibraryPackMemberRepository(self.db)

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.temp.cleanup()

    async def test_fresh_schema_exactly_matches_plot_row(self):
        await self.db.validate_schema([PlotTemplateRow])
        async with self.db.conn.execute("PRAGMA table_info(plot_templates)") as cursor:
            columns = {item["name"] for item in await cursor.fetchall()}
        self.assertEqual(columns, model_columns(PlotTemplateRow))
        self.assertNotIn("owner_world_uid", columns)

    async def test_insert_read_update_delete_preserves_uid_and_nested_body(self):
        uid = library_uid(_PLOTS, "shared", pack_uid=pack("user.plots").pack_uid)
        original = row(uid, source_file="authoring/shared.json")
        await self.repo.insert(original)
        stored = await self.repo.get_by_uid(uid)
        self.assertEqual(stored, original)
        body = PlotTemplate.model_validate(stored.data)
        self.assertEqual(body.main_building.foundation_depth, 0)
        self.assertTrue(body.secondary_buildings[0].porch_has_roof)
        edited = replace(stored, system_name="renamed", display_name="Edited")
        await self.repo.save(edited)
        self.assertEqual(await self.repo.get_by_uid(uid), edited)
        self.assertIsNone(await self.repo.get_by_uid("shared"))
        await self.repo.delete(uid)
        self.assertIsNone(await self.repo.get_by_uid(uid))

    async def test_same_names_in_same_or_other_pack_preserve_member_identity(self):
        first_pack, second_pack = pack("user.first"), pack("user.second")
        first = library_uid(_PLOTS, "shared", pack_uid=first_pack.pack_uid)
        copied = runtime_uid()
        second = library_uid(_PLOTS, "shared", pack_uid=second_pack.pack_uid)
        async with self.db.transaction():
            await self.packs.insert_missing([first_pack, second_pack])
            for uid, owner in ((first, first_pack), (copied, first_pack), (second, second_pack)):
                await self.members.insert_missing([
                    LibraryPackMemberRow(uid, owner.pack_uid, _PLOTS.value, "shared"),
                ])
                await self.repo.insert(row(uid))
        stored = await self.repo.list_all()
        self.assertEqual([item.template_uid for item in stored], sorted((first, copied, second)))
        self.assertEqual({item.system_name for item in stored}, {"shared"})
        self.assertEqual((await self.members.get_by_uid(copied)).pack_uid, first_pack.pack_uid)

    async def test_duplicate_uid_rejects_insert_without_replacing_existing_body(self):
        uid = runtime_uid()
        original = row(uid)
        await self.repo.insert(original)
        with self.assertRaises(sqlite3.IntegrityError):
            async with self.db.transaction():
                await self.repo.insert(replace(original, display_name="Cannot replace"))
        self.assertEqual(await self.repo.get_by_uid(uid), original)

    async def test_body_and_membership_rollback_together_in_caller_uow(self):
        owner = pack("user.rollback")
        uid = library_uid(_PLOTS, "shared", pack_uid=owner.pack_uid)
        with self.assertRaisesRegex(ValueError, "abort"):
            async with self.db.transaction():
                await self.packs.insert_missing([owner])
                await self.members.insert_missing([
                    LibraryPackMemberRow(uid, owner.pack_uid, _PLOTS.value, "shared"),
                ])
                await self.repo.insert(row(uid))
                raise ValueError("abort")
        self.assertIsNone(await self.repo.get_by_uid(uid))
        self.assertIsNone(await self.members.get_by_uid(uid))
        self.assertIsNone(await self.packs.get_by_uid(owner.pack_uid))

    async def test_container_registers_lazy_providers_without_changing_old_methods(self):
        container = Container(None, self.db)
        for name in ("plot_template_repository", "building_template_repository",
                     "structure_template_repository"):
            provider = getattr(container, name)
            self.assertIs(provider(), provider())
        repo = container.plot_template_repository()
        original = row(runtime_uid())
        await repo.insert(original)
        self.assertEqual(await repo.get_by_uid(original.template_uid), original)
        other = Container(None, self.db)
        self.assertIsNot(other.plot_template_repository(), repo)


class PlotIdentityTest(unittest.TestCase):
    def test_domain_and_owner_are_part_of_central_identity(self):
        first, second = pack("user.first").pack_uid, pack("user.second").pack_uid
        uid = library_uid(_PLOTS, "shared", pack_uid=first)
        self.assertEqual(uid, library_uid(_PLOTS, "shared", pack_uid=first))
        self.assertNotEqual(uid, library_uid(_PLOTS, "shared", pack_uid=second))
        self.assertNotEqual(uid, library_uid(LibraryKind.BUILDING_TEMPLATES, "shared", pack_uid=first))

    def test_domain_migration_and_pack_remap_reuse_source_uid_not_readable_name(self):
        target = pack("world.target").pack_uid
        source = library_uid(LibraryKind.BUILDING_TEMPLATES, "old", pack_uid=pack("user.source").pack_uid)
        plot_uid = remapped_library_uid(_PLOTS, target_pack_uid=target, source_template_uid=source)
        self.assertEqual(plot_uid, remapped_library_uid(_PLOTS, target_pack_uid=target,
                                                       source_template_uid=source))
        self.assertNotEqual(plot_uid, remapped_library_uid(LibraryKind.BUILDING_TEMPLATES,
                                                         target_pack_uid=target, source_template_uid=source))
        copied = runtime_uid()
        self.assertNotEqual(plot_uid, remapped_library_uid(_PLOTS, target_pack_uid=target,
                                                         source_template_uid=copied))


if __name__ == "__main__":
    unittest.main()
