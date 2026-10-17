"""Step 6 N+1 regressions through production bundle, SQLite and pack paths."""

import json
import tempfile
import unittest
from pathlib import Path

from app.application.jsonValidation.resolve import UnresolvedModelError
from app.application.jsonValidation.worldRow import location_types
from app.application.worldData.pack.bake.locationsIndexBake import build_locations_index
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationsIndexRead import load_locations_index
from app.application.worldData.render.pack.locationPinOverlay import overlay_location_pins
from app.core.container import Container
from app.dataModel.locations.locationType.worldLocationTypeRegistry import WorldLocationTypeRegistry
from app.dataModel.registryKey import RegistryKey
from app.db.database import Database
from app.db.models.world import World
from app.db.repositories.sqlite.namedLocationRepository import SqliteNamedLocationRepository


class LocationTypeNPlusOneTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(str(Path(self.tmp.name) / "n-plus-one.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        container = Container(None, self.db)
        self.worlds = container.world_repository()
        self.bundle = container.world_bundle_service()
        self.locations = SqliteNamedLocationRepository(self.db)

    def fixture(self, registry, locations):
        return {"world": {
            "world_uid": "source-n-plus-one", "name": "N+1 World",
            "created_at": "2026-10-18", "location_type_registry": registry,
        }, "locations": locations}

    def location(self, uid, key, **fields):
        return {"location_uid": uid, "display_name": uid,
                "system_location_type": key, **fields}

    async def import_fixture(self, fixture):
        # The same N+1 data must pass both preview and the actual import.
        preview = await self.bundle.import_bundle(fixture, validate_only=True)
        self.assertTrue(preview.valid, preview.issues)
        self.assertEqual(await self.worlds.get_all(), [])
        results, rolled_back = await self.bundle.import_bundle(fixture)
        self.assertFalse(rolled_back, results)
        for section, result in results.items():
            self.assertEqual(result.failed, 0, (section, result.errors))
        world, = await self.worlds.get_all()
        exported = await self.bundle.export(world.world_uid)
        rows = await self.locations.get_by_world(world.world_uid)
        return world, exported, {row.display_name: row for row in rows}

    async def test_new_type_and_new_parent_survive_import_sql_export_and_pack(self):
        root_key, leaf_key = "author-realm-v2", "author-sanctuary-v2"
        engine = WorldLocationTypeRegistry.canonical_engine()
        for key in (root_key, leaf_key):
            self.assertIsNone(engine.entry_for(key))
        registry_wire = [
            {"system_type": root_key, "display_type": "Авторский регион", "parent_types": [None]},
            {"system_type": leaf_key, "display_type": "Авторское место", "parent_types": [root_key]},
        ]
        world, exported, rows = await self.import_fixture(self.fixture(registry_wire, [
            self.location("author-root", root_key, map_x=10, map_y=20),
            self.location("author-leaf", leaf_key, parent_location_uid="author-root", map_x=30, map_y=40),
        ]))
        registry = location_types(world)
        self.assertTrue(registry.allows_parent(leaf_key, root_key))
        self.assertEqual(rows["author-leaf"].parent_location_uid, rows["author-root"].location_uid)
        stored = {entry["system_type"]: entry for entry in exported["world"]["location_type_registry"]}
        for source in registry_wire:
            entry = registry.entry_for(source["system_type"])
            self.assertIsInstance(entry.system_type, RegistryKey)
            self.assertEqual(entry.parent_types, source["parent_types"])
            for field, value in source.items():
                self.assertEqual(stored[source["system_type"]][field], value)
        for row in rows.values():
            self.assertIs(type(row.system_location_type), str)
        exported_types = {row["display_name"]: row["system_location_type"] for row in exported["locations"]}
        self.assertEqual(exported_types, {"author-root": root_key, "author-leaf": leaf_key})
        paths = WorldPackPaths(Path(self.tmp.name) / "pack", world.world_uid)
        index = build_locations_index(list(rows.values()), world)
        WorldPackWriter(paths).write_locations_index(index)
        loaded = load_locations_index(paths)
        self.assertEqual(loaded, index)
        overlay = overlay_location_pins(loaded, list(rows.values()))
        self.assertEqual({pin.system_location_type for pin in overlay.locations}, {root_key, leaf_key})
        self.assertTrue(all(isinstance(pin.system_location_type, RegistryKey) for pin in overlay.locations))
        self.assertEqual(json.loads(paths.locations_index_path().read_text(encoding="utf-8")),
                         index.model_dump(mode="json"))

    async def test_existing_type_accepts_new_parent_and_new_subtype(self):
        parent_key, subtype = "author-enclave-v3", "author-observatory-v3"
        building_key = WorldLocationTypeRegistry.SYSTEM_TYPE_BUILDING
        world, exported, rows = await self.import_fixture(self.fixture([
            {"system_type": parent_key, "display_type": "Enclave", "parent_types": [None]},
            {"system_type": building_key, "display_type": "Building",
             "parent_types": [parent_key], "subtypes": [{"system_subtype": subtype}]},
        ], [
            self.location("enclave", parent_key),
            self.location("observatory", building_key, system_location_subtype=subtype,
                          parent_location_uid="enclave"),
        ]))
        registry = location_types(world)
        self.assertEqual(registry.entry_for(building_key).parent_types, [parent_key])
        self.assertTrue(registry.allows_parent(building_key, parent_key))
        self.assertIsNotNone(registry.subtype_for(building_key, subtype))
        self.assertEqual(rows["observatory"].system_location_subtype, subtype)
        by_name = {row["display_name"]: row for row in exported["locations"]}
        self.assertEqual(by_name["observatory"]["system_location_subtype"], subtype)

    async def test_new_type_selects_existing_payload_contract_without_enum_error(self):
        key, subtype = "author-floating-settlement-v4", "author-sky-dock-v4"
        world, exported, rows = await self.import_fixture(self.fixture([
            {"system_type": key, "display_type": "Floating settlement", "parent_types": [None],
             "payload_kind": "settlement", "is_inhabited": False,
             "subtypes": [{"system_subtype": subtype}]},
        ], [self.location("sky-dock", key, system_location_subtype=subtype,
                          location_payload={"is_inhabited": False})]))
        self.assertEqual(location_types(world).entry_for(key).payload_kind.value, "settlement")
        self.assertEqual(rows["sky-dock"].system_location_type, key)
        self.assertEqual(rows["sky-dock"].system_location_subtype, subtype)
        self.assertFalse(rows["sky-dock"].location_payload["is_inhabited"])
        record, = exported["locations"]
        self.assertEqual(record["system_location_type"], key)
        self.assertEqual(record["system_location_subtype"], subtype)
        self.assertFalse(record["location_payload"]["is_inhabited"])

    async def test_n_plus_one_is_world_scoped_and_historical_pack_stays_readable(self):
        key = "author-world-specific-type-v5"
        world, _, rows = await self.import_fixture(self.fixture([
            {"system_type": key, "display_type": "Author type", "parent_types": [None]},
        ], [self.location("custom-pin", key, map_x=1, map_y=2)]))
        paths = WorldPackPaths(Path(self.tmp.name) / "historical-pack", world.world_uid)
        index = build_locations_index(list(rows.values()), world)
        WorldPackWriter(paths).write_locations_index(index)
        other_world = World(world_uid="unextended-world", name="Other", created_at="now")
        self.assertIsNone(location_types(other_world).entry_for(key))
        with self.assertRaises(UnresolvedModelError):
            build_locations_index(list(rows.values()), other_world)
        # Removing the type from today's registry cannot invalidate a baked snapshot.
        self.assertEqual(load_locations_index(paths), index)


if __name__ == "__main__":
    unittest.main()
