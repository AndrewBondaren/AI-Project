"""P2a: payload storage against the main SQL schema, without copied DDL."""

import json
import tempfile
import unittest
from pathlib import Path

from app.db.database import Database
from app.db.mapper import model_columns
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.sqlite.namedLocationRepository import SqliteNamedLocationRepository
from app.application.worldData.namedLocationService import NamedLocationService
from app.application.worldData.locationPayloadAccess import settlement_payload, district_payload
from app.application.worldData.context.locationScope import settlement_context
from app.application.worldData.generators.assemblers.citySkeleton import settlement_skeleton_pojo
from app.dataModel.locations.namedLocation import BundleNamedLocation


class LocationPayloadSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "payload.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        await self.db.conn.execute(
            "INSERT INTO worlds(world_uid, name, created_at) VALUES (?, ?, ?)",
            ("world", "World", "2026-10-06"),
        )
        await self.db.conn.commit()
        self.repo = SqliteNamedLocationRepository(self.db)

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.tmp.cleanup()

    def location(self, uid, payload):
        return NamedLocation(
            location_uid=uid, world_uid="world", display_name=uid,
            system_location_type="settlement", created_at="2026-10-06",
            location_payload=payload,
        )

    async def test_schema_matches_model_and_nullable_text_column(self):
        await self.db.validate_schema([World, NamedLocation])
        async with self.db.conn.execute("PRAGMA table_info(named_locations)") as cursor:
            columns = {row["name"]: row for row in await cursor.fetchall()}
        self.assertEqual(set(columns), model_columns(NamedLocation))
        self.assertEqual(columns["location_payload"]["type"], "TEXT")
        self.assertEqual(columns["location_payload"]["notnull"], 0)

    async def test_roundtrip_distinguishes_null_empty_and_nested_json(self):
        for uid, payload in (("null", None), ("empty", {}), ("nested", {
            "system_city_size": "custom-size", "is_inhabited": False,
            "plot_counts": {"custom-plot": 2}, "typical_districts": [],
            "architectural_style": "Камень",
        })):
            with self.subTest(uid=uid):
                await self.repo.upsert(self.location(uid, payload))
                stored = await self.repo.get_by_id(uid)
                self.assertEqual(stored.location_payload, payload)
                async with self.db.conn.execute(
                    "SELECT location_payload FROM named_locations WHERE location_uid=?", (uid,),
                ) as cursor:
                    raw = (await cursor.fetchone())["location_payload"]
                if payload is None:
                    self.assertIsNone(raw)
                else:
                    self.assertIsInstance(raw, str)
                    self.assertEqual(json.loads(raw), payload)

    async def test_payload_update_preserves_generic_location_fields(self):
        row = self.location("updated", {"system_city_size": "small"})
        row.system_economic_tier = "custom-tier"
        row.parent_wall_material = "stone"
        await self.repo.upsert(row)
        row.location_payload = {"system_city_size": "large", "is_inhabited": False}
        await self.repo.upsert(row)
        stored = await self.repo.get_by_id(row.location_uid)
        self.assertEqual(stored.location_payload, row.location_payload)
        self.assertEqual(stored.system_economic_tier, "custom-tier")
        self.assertEqual(stored.parent_wall_material, "stone")
        row.location_payload = None
        await self.repo.upsert(row)
        self.assertIsNone((await self.repo.get_by_id(row.location_uid)).location_payload)

    async def test_flat_import_moves_all_settlement_groups_to_payload(self):
        service = NamedLocationService(self.repo)
        wire = {
            "location_uid": "imported", "display_name": "Imported",
            "system_location_type": "settlement", "system_city_size": "large",
            "settlement_density": "dense", "dominant_material": "stone",
            "architectural_style": "gothic", "frontage_type_order": ["road"],
            "structure_counts": {"plot": 2}, "structure_priority": {"plot": 3},
            "perimeter_barrier": {"template": "stone_fence", "probability": 1.0},
            "typical_districts": [{"district_type": "civic"}],
            "system_settlement_specializations": ["extract"], "system_economic_tier": "custom-tier",
        }
        result = await service.import_from_json("world", [wire])
        self.assertEqual(result.failed, 0, result.errors)
        stored = await self.repo.get_by_id("imported")
        payload = settlement_payload(stored)
        self.assertEqual(payload.system_city_size, "large")
        self.assertEqual(payload.plot_counts, {"plot": 2})
        self.assertEqual(payload.plot_priority, {"plot": 3})
        self.assertEqual(payload.perimeter_barrier.template, "stone_fence")
        self.assertEqual(payload.typical_districts[0].district_type, "civic")
        self.assertEqual(payload.system_settlement_specializations[0].system_specialization, "extract")
        self.assertIsNone(stored.system_city_size)
        self.assertIsNone(stored.plot_counts)
        self.assertEqual(stored.system_economic_tier, "custom-tier")
        self.assertEqual(settlement_skeleton_pojo(stored).architectural_style, "gothic")
        world = World(world_uid="world", name="World", created_at="2026-10-06")
        ctx = settlement_context(world, stored)
        self.assertEqual(ctx.system_city_size, "large")
        self.assertEqual(ctx.settlement_density, payload.settlement_density)

    async def test_crud_updates_payload_without_erasing_other_fields(self):
        service = NamedLocationService(self.repo)
        await service.create("world", {
            "location_uid": "crud", "display_name": "CRUD", "system_location_type": "settlement",
            "system_city_size": "small", "plot_counts": {"plot": 2},
            "system_economic_tier": "custom-tier",
        })
        await service.update("world", "crud", {"system_city_size": "large", "is_inhabited": False})
        stored = await self.repo.get_by_id("crud")
        self.assertEqual(stored.location_payload["system_city_size"], "large")
        self.assertFalse(stored.location_payload["is_inhabited"])
        self.assertEqual(stored.location_payload["plot_counts"], {"plot": 2})
        self.assertEqual(stored.system_economic_tier, "custom-tier")
        await service.update("world", "crud", {"system_city_size": None})
        self.assertIsNone(settlement_payload(await self.repo.get_by_id("crud")).system_city_size)

    async def test_complex_recipe_default_and_explicit_override(self):
        base = {"location_uid": "complex", "display_name": "Complex",
                "system_location_type": "location_complex", "system_location_subtype": "ruins"}
        inferred = BundleNamedLocation.model_validate(base)
        self.assertFalse(inferred.location_payload.is_inhabited)
        explicit = BundleNamedLocation.model_validate({**base, "is_inhabited": True})
        self.assertTrue(explicit.location_payload.is_inhabited)

    async def test_partial_update_migrates_legacy_values_without_losing_them(self):
        legacy = self.location("legacy", None)
        legacy.system_city_size = "small"
        legacy.plot_counts = {"plot": 2}
        await self.repo.upsert(legacy)
        await NamedLocationService(self.repo).update("world", "legacy", {"display_name": "Renamed"})
        stored = await self.repo.get_by_id("legacy")
        self.assertEqual(stored.display_name, "Renamed")
        self.assertEqual(settlement_payload(stored).system_city_size, "small")
        self.assertEqual(settlement_payload(stored).plot_counts, {"plot": 2})
        self.assertIsNone(stored.plot_counts)

    async def test_import_resolves_custom_world_payload_kind(self):
        world = World(world_uid="world", name="World", created_at="2026-10-06",
                      location_type_registry=[{
                          "system_type": "elven_city", "display_type": "City", "payload_kind": "settlement",
                      }])
        loc = NamedLocationService._from_wire({
            "location_uid": "custom", "display_name": "Custom", "system_location_type": "elven_city",
            "system_city_size": "medium",
        }, world_uid="world", world=world)
        await self.repo.upsert(loc)
        self.assertEqual(settlement_context(world, await self.repo.get_by_id("custom")).system_city_size,
                         "medium")

    async def test_payload_wins_over_legacy_columns_and_invalid_payload_fails(self):
        row = self.location("priority", {"system_city_size": "large"})
        row.system_city_size = "small"
        self.assertEqual(settlement_skeleton_pojo(row).system_city_size, "large")
        row.location_payload = None
        self.assertEqual(settlement_payload(row).system_city_size, "small")
        row.location_payload = {"plot_counts": {"plot": "invalid"}}
        with self.assertRaises(ValueError):
            settlement_payload(row)

    async def test_district_flat_wire_reaches_typed_storage(self):
        topology = {"cell_x": 0, "cell_y": 0, "origin_x": 1, "origin_y": 2,
                    "width_fine": 30, "depth_fine": 40, "ground_z": -1,
                    "template_system_name": "custom", "slot_index": 0}
        service = NamedLocationService(self.repo)
        await service.create("world", {"location_uid": "district", "display_name": "District",
                                       "system_location_type": "district", "district_topology": topology})
        stored = await self.repo.get_by_id("district")
        self.assertIsNone(stored.district_topology)
        self.assertEqual(district_payload(stored).district_topology.width_fine, 30)


if __name__ == "__main__":
    unittest.main()
