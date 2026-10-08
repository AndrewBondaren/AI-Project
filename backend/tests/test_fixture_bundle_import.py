"""Real bundle import against the current SQL schema and POJO defaults."""

import json
import tempfile
import unittest
from pathlib import Path

from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import location_types, materials, terrain
from app.application.jsonValidation.worldSlices import (
    facade_world_slices,
    resolve_json_blob_world,
    resolve_multi_column_world,
    resolve_registry_dict_world,
    resolve_registry_list_world,
)
from app.core.container import Container
from app.dataModel.locations.locationType.worldLocationTypeRegistry import WorldLocationTypeRegistry
from app.db.database import Database
from app.db.models.buildingTemplate import BuildingTemplateRow
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.race import Race
from app.db.models.reliefTemplate import ReliefTemplateRow
from app.db.models.state import State
from app.db.models.world import World
from app.db.models.world_perk import WorldPerk
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
        container = Container(None, self.db)
        self.repo = container.world_repository()
        self.worlds = container.world_service()
        self.bundle = container.world_bundle_service()

    async def test_all_eight_bundles_import_and_export_every_section(self):
        names = (
            "world_defaults_test", "world_template", "world_terrain_test", "world_test",
            "world_test_all", "world_test_002", "world_test_gen_003", "world_test_gen_noloc",
        )
        for name in names:
            with self.subTest(fixture=name):
                fixture = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
                # Each bundle starts with an empty database and the production handler registry.
                db = Database(str(Path(self.tmp.name) / f"{name}.sqlite"))
                await db.connect()
                try:
                    await db.apply_migrations()
                    await db.validate_schema([
                        World, State, NamedLocation, ConnectionNode, ConnectionEdge,
                        ReliefTemplateRow, BuildingTemplateRow, Race, WorldPerk,
                    ])
                    container = Container(None, db)
                    repo = container.world_repository()
                    bundle = container.world_bundle_service()
                    results, rolled_back = await bundle.import_bundle(fixture)
                    self.assertFalse(rolled_back, {key: value.errors for key, value in results.items()})
                    self.assertEqual(set(results), set(fixture))
                    for key, result in results.items():
                        self.assertEqual(result.failed, 0, result.errors)
                        self.assertEqual(result.succeeded, 1 if key == "world" else len(fixture[key]))
                    worlds = await repo.get_all()
                    world = next(w for w in worlds if w.name == fixture["world"]["name"])
                    exported = await bundle.export(world.world_uid)
                    for key, identity, pojo in (
                        ("material_registry", "system_material", materials(world)),
                        ("terrain_registry", "system_terrain", terrain(world)),
                    ):
                        stored = {row[identity]: row for row in exported["world"][key]}
                        canonical = type(pojo).canonical_defaults().model_dump(mode="json")
                        self.assertTrue({row[identity] for row in canonical} <= stored.keys())
                        for row in fixture["world"].get(key, []):
                            for field, value in row.items():
                                self.assertEqual(stored[row[identity]][field], value, (name, key, field))
                    for key, rows in fixture.items():
                        if key == "world":
                            continue
                        self.assertEqual(len(exported[key]), len(rows), key)
                        if key in ("race_templates", "perk_templates"):
                            by_uid = {row["template_uid"]: row for row in exported[key]}
                            for row in rows:
                                self.assertNotIn("world_uid", row)
                                for field, value in row.items():
                                    self.assertEqual(by_uid[row["template_uid"]][field], value, field)

                    registry = location_types(world)
                    engine = WorldLocationTypeRegistry.canonical_engine()
                    for subtype in ("city", "village", "underground_city"):
                        recipe = registry.subtype_for("settlement", subtype)
                        canonical = engine.subtype_for("settlement", subtype)
                        self.assertEqual(recipe.typical_district_types, canonical.typical_district_types)
                        self.assertEqual(recipe.required_structure_types, canonical.required_structure_types)
                        for size, footprint in canonical.footprint_by_size.items():
                            self.assertEqual(recipe.footprint_by_size[size], footprint)
                        if name in ("world_test_all", "world_test_002"):
                            self.assertEqual(recipe.footprint_by_size["huge"], 0.9 if subtype == "village" else 8.0)
                            self.assertIn("huge", {row["system_size"] for row in world.city_size_registry})
                    locations = {row["location_uid"]: row for row in exported["locations"]}
                    for source in fixture.get("locations", []):
                        row = locations[source["location_uid"]]
                        parent_uid = row["parent_location_uid"]
                        parent_type = locations[parent_uid]["system_location_type"] if parent_uid else None
                        self.assertTrue(registry.allows_parent(row["system_location_type"], parent_type),
                                        (name, row["location_uid"], row["system_location_type"], parent_type))
                        for field, value in (source.get("location_payload") or {}).items():
                            self.assertEqual(row["location_payload"][field], value, (name, field))
                finally:
                    await db.disconnect()

    def test_combined_fixture_is_reproducible(self):
        from scripts.build_world_test_all_fixture import build

        stored = json.loads((FIXTURES / "world_test_all.json").read_text(encoding="utf-8"))
        self.assertEqual(build(), stored)

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
