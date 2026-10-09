"""Payload storage against the main SQL schema, without copied DDL."""

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
from app.application.worldData.locationPayloadAccess import settlement_payload, district_payload, payload_field_names
from app.application.cascade.locationScope import settlement_context
from app.application.worldData.settlementSkeletonAccess import settlement_skeleton_pojo, resolved_settlement_skeleton
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
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
        self.assertTrue(set(columns).isdisjoint(payload_field_names()))
        self.assertTrue(set(BundleNamedLocation.model_fields).isdisjoint(payload_field_names()))
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

    async def test_source_and_resolved_skeletons_preserve_authored_storage(self):
        row = self.location("skeleton", {
            "plot_counts": {"plot": 2}, "dominant_material": "marble",
            "settlement_density": "sparse",
        })
        row.system_economic_tier = "poor"
        row.system_location_mood = "prosperous"
        source = settlement_skeleton_pojo(row)
        resolved = resolved_settlement_skeleton(
            row, economic_tier="quality", settlement_density="dense",
        )
        cleared = resolved_settlement_skeleton(
            row, economic_tier=None, settlement_density=None,
        )
        self.assertIsInstance(resolved, SettlementSkeleton)
        self.assertEqual((source.economic_tier, source.settlement_density, source.dominant_material),
                         ("poor", "sparse", "marble"))
        self.assertEqual((resolved.economic_tier, resolved.settlement_density, resolved.system_location_mood),
                         ("quality", "dense", "prosperous"))
        self.assertIsNone(resolved.dominant_material)
        self.assertIsNone(cleared.economic_tier)
        self.assertIsNone(cleared.settlement_density)
        resolved.plot_counts["plot"] = 3
        self.assertEqual(source.plot_counts, {"plot": 2})
        self.assertEqual(row.location_payload["plot_counts"], {"plot": 2})

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
        self.assertNotIn("system_city_size", model_columns(NamedLocation))
        self.assertNotIn("plot_counts", model_columns(NamedLocation))
        self.assertEqual(stored.system_economic_tier, "custom-tier")
        self.assertEqual(settlement_skeleton_pojo(stored).architectural_style, "gothic")
        world = World(world_uid="world", name="World", created_at="2026-10-06")
        world.economic_tier_registry = [{"system_tier": "custom-tier", "display_tier": "Custom", "base_value": 10}]
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

    async def test_partial_generic_update_initializes_null_payload(self):
        await self.repo.upsert(self.location("null-payload", None))
        await NamedLocationService(self.repo).update("world", "null-payload", {"display_name": "Renamed"})
        stored = await self.repo.get_by_id("null-payload")
        self.assertEqual(stored.display_name, "Renamed")
        self.assertIsNone(settlement_payload(stored).system_city_size)
        self.assertIsNone(settlement_payload(stored).plot_counts)
        self.assertTrue(settlement_payload(stored).is_inhabited)

    async def test_import_rejects_recipe_default_false_with_specializations(self):
        service = NamedLocationService(self.repo)
        base = {"display_name": "Complex", "system_location_type": "location_complex",
                "system_location_subtype": "ruins", "system_settlement_specializations": ["extract"]}
        result = await service.import_from_json("world", [
            {**base, "location_uid": "invalid"},
            {**base, "location_uid": "inhabited", "is_inhabited": True},
        ])
        self.assertEqual((result.succeeded, result.failed), (1, 1))
        self.assertIn("requires is_inhabited=true", result.errors[0].message)
        self.assertIsNone(await self.repo.get_by_id("invalid"))
        self.assertTrue(settlement_payload(await self.repo.get_by_id("inhabited")).is_inhabited)

    async def test_crud_rejects_invalid_liveness_without_persisting(self):
        service = NamedLocationService(self.repo)
        await service.create("world", {
            "location_uid": "live", "display_name": "Live", "system_location_type": "settlement",
            "system_settlement_specializations": ["extract"],
        })
        with self.assertRaisesRegex(ValueError, "requires is_inhabited=true"):
            await service.update("world", "live", {"is_inhabited": False})
        self.assertTrue(settlement_payload(await self.repo.get_by_id("live")).is_inhabited)
        await service.update("world", "live", {
            "is_inhabited": False, "system_settlement_specializations": [],
        })
        stored = await self.repo.get_by_id("live")
        self.assertFalse(settlement_payload(stored).is_inhabited)
        stored.location_payload["system_settlement_specializations"] = ["extract"]
        with self.assertRaisesRegex(ValueError, "requires is_inhabited=true"):
            settlement_context(World(world_uid="world", name="World", created_at="2026-10-07"), stored)

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

    async def test_resolved_inhabited_flag_roundtrips_to_skeleton_and_survives_crud(self):
        world = World(world_uid="world", name="World", created_at="2026-10-07",
                      location_type_registry=[{
                          "system_type": "custom_site", "display_type": "Site", "payload_kind": "settlement",
                          "is_inhabited": True, "subtypes": [{"system_subtype": "abandoned", "is_inhabited": False}],
                      }])
        service = NamedLocationService(self.repo)
        for uid, subtype, expected in (("type-default", None, True), ("subtype-default", "abandoned", False)):
            with self.subTest(uid=uid):
                row = service._from_wire({
                    "location_uid": uid, "display_name": "Site", "system_location_type": "custom_site",
                    "system_location_subtype": subtype,
                }, world_uid="world", world=world)
                await self.repo.upsert(row)
                stored = await self.repo.get_by_id(uid)
                self.assertIs(stored.location_payload["is_inhabited"], expected)
                self.assertIs(settlement_skeleton_pojo(stored).is_inhabited, expected)
                self.assertIs(resolved_settlement_skeleton(
                    stored, economic_tier="standard", settlement_density="medium",
                ).is_inhabited, expected)
        await service.create("world", {
            "location_uid": "partial", "display_name": "Site", "system_location_type": "settlement",
        })
        await service.update("world", "partial", {"display_name": "Renamed"})
        self.assertTrue(settlement_payload(await self.repo.get_by_id("partial")).is_inhabited)

    async def test_runtime_binds_payload_for_settlement_and_complex(self):
        world = World(world_uid="world", name="World", created_at="2026-10-07")
        world.economic_tier_registry = [{"system_tier": "custom-tier", "display_tier": "Custom", "base_value": 10}]
        world.material_registry = [{"system_material": "marble", "display_name": "Marble", "material_category": "solid"}]
        for kind in ("settlement", "location_complex"):
            row = self.location(kind, {"system_city_size": "large", "settlement_density": "dense",
                                       "dominant_material": "marble"})
            row.system_location_type = kind
            row.system_economic_tier = "custom-tier"
            ctx = settlement_context(world, row)
            self.assertEqual((ctx.system_city_size, ctx.settlement_density, ctx.dominant_material),
                             ("large", "dense", "marble"))
            for name in ("system_city_size", "settlement_density", "dominant_material"):
                self.assertEqual(ctx.provenance[name][1], f"SettlementPayload.{name}")
            self.assertEqual(ctx.provenance["economic_tier"][1], "BundleNamedLocation.system_economic_tier")

    async def test_payload_is_the_only_source_and_invalid_payload_fails(self):
        row = self.location("priority", {"system_city_size": "large"})
        # A stray attribute on a runtime object must never restore the removed fallback.
        row.system_city_size = "small"
        self.assertEqual(settlement_skeleton_pojo(row).system_city_size, "large")
        row.location_payload = None
        self.assertIsNone(settlement_payload(row).system_city_size)
        self.assertFalse(settlement_payload(row).is_inhabited)
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
        self.assertNotIn("district_topology", model_columns(NamedLocation))
        self.assertEqual(district_payload(stored).district_topology.width_fine, 30)


if __name__ == "__main__":
    unittest.main()
