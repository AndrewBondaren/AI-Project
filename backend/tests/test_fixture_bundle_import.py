"""Real bundle import against the current SQL schema and POJO defaults."""

import json
import tempfile
import unittest
from pathlib import Path

from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import materials, terrain
from app.application.jsonValidation.worldSlices import (
    facade_world_slices,
    resolve_json_blob_world,
    resolve_multi_column_world,
    resolve_registry_dict_world,
    resolve_registry_list_world,
)
from app.application.worldData.bundle.entity.sections import WorldSectionHandler
from app.application.worldData.worldBundleService import WorldBundleService
from app.application.worldData.worldService import WorldService
from app.db.database import Database
from app.db.models.world import World
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


class FixtureBundleImportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(str(Path(self.tmp.name) / "fixtures.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        await self.db.validate_schema([World])
        self.repo = SqliteWorldRepository(self.db)
        self.worlds = WorldService(self.repo)
        self.bundle = WorldBundleService(self.db, self.worlds, [WorldSectionHandler(self.worlds)])

    def defaults_fixture(self):
        fixture = json.loads((FIXTURES / "world_defaults_test.json").read_text(encoding="utf-8"))
        self.assertEqual(set(fixture["world"]), {"world_uid", "name", "created_at"})
        return fixture

    async def import_world(self, fixture):
        self.assertEqual(set(fixture), {"world"})
        results, rolled_back = await self.bundle.import_bundle(fixture)
        self.assertFalse(rolled_back)
        self.assertEqual(set(results), {"world"})
        self.assertEqual(results["world"].succeeded, 1, results["world"].errors)
        self.assertEqual(results["world"].failed, 0)
        # Read through a fresh repository instance, not an in-memory World object.
        return await SqliteWorldRepository(self.db).get_by_id(fixture["world"]["world_uid"])

    async def test_defaults_fixture_imports_and_reads_all_declared_world_defaults(self):
        world = await self.import_world(self.defaults_fixture())
        self.assertIsNotNone(world)
        for world_slice in facade_world_slices():
            with self.subTest(schema=world_slice.schema_id):
                match world_slice.wire_kind:
                    case "multi_column":
                        expected = world_slice.pojo_cls()
                        actual = resolve_multi_column_world(world, world_slice.pojo_cls)
                    case "registry_list":
                        expected = world_slice.empty_factory()
                        actual = resolve_registry_list_world(world, world_slice.pojo_cls)
                    case "registry_dict":
                        expected = world_slice.empty_factory()
                        actual = resolve_registry_dict_world(world, world_slice.pojo_cls)
                    case "json_blob":
                        expected = world_slice.empty_factory()
                        actual = resolve_json_blob_world(world, world_slice.pojo_cls)
                    case _:
                        self.fail(f"Unhandled world slice kind: {world_slice.wire_kind}")
                self.assertEqual(actual.model_dump(mode="json"), expected.model_dump(mode="json"))
                if world_slice.canonical_overlay_id_field:
                    # These libraries must be stored in full, not supplied only on read.
                    self.assertEqual(getattr(world, world_slice.world_keys[0]),
                                     expected.model_dump(mode="json"))

    async def test_partial_libraries_persist_overrides_and_survive_unrelated_update(self):
        fixture = self.defaults_fixture()
        fixture["world"]["material_registry"] = [{
            "system_material": "wood", "flammable": False, "density": 77,
        }]
        fixture["world"]["terrain_registry"] = [{
            "system_terrain": "shore_river", "travel_modifier": 0,
        }]
        world = await self.import_world(fixture)
        self.assertIsNotNone(materials(world).entry_for("sand"))
        self.assertIsNotNone(terrain(world).entry_for("shore_sea"))
        self.assertFalse(materials(world).entry_for("wood").flammable)
        self.assertEqual(materials(world).entry_for("wood").density, 77)
        self.assertEqual(terrain(world).entry_for("shore_river").travel_modifier, 0)
        await self.worlds.update(world.world_uid, {"name": "Renamed"})
        after = await self.repo.get_by_id(world.world_uid)
        self.assertEqual(after.name, "Renamed")
        self.assertEqual(after.material_registry, world.material_registry)
        self.assertEqual(after.terrain_registry, world.terrain_registry)

    async def test_unknown_default_dependency_is_rejected_before_persistence(self):
        fixture = self.defaults_fixture()
        fixture["world"]["hydrology"] = {"default_rivers": {"shore": {
            "system_terrain": "shore_river", "system_material": "missing",
        }}}
        with self.assertRaises(ImportValidationError):
            await self.bundle.import_bundle(fixture)
        self.assertIsNone(await self.repo.get_by_id(fixture["world"]["world_uid"]))


if __name__ == "__main__":
    unittest.main()
