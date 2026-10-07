"""P1 typed payload contract — tz_locations §Payload per type."""

import unittest
from dataclasses import replace

from pydantic import ValidationError

from app.dataModel.cascade.cascadeGraph import cascade_channels
from app.dataModel.locations.locationPayload import LocationPayload
from app.dataModel.locations.locationFootprintPolicy import is_settlement_map_site, uses_settlement_fine_footprint
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import is_settlement_outdoor_target, packing_targets
from app.application.worldData.settlementOutdoor.settlementOutdoorTypes import is_district_location
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.application.worldData.render.lightMapPins import location_mark_pins
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin
from app.dataModel.locations.locationType.locationTypeEntry import LocationTypeEntry
from app.dataModel.locations.locationType.worldLocationTypeRegistry import WorldLocationTypeRegistry
from app.dataModel.locations.payloadKind import PayloadKind
from app.dataModel.locations.settlement.district.districtPayload import DistrictPayload
from app.dataModel.locations.settlement.district.districtTopologySlot import DistrictTopologySlot
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton


class LocationPayloadTests(unittest.TestCase):
    def test_footprint_selection_uses_contract_not_subtype_or_legacy_name(self):
        for key in ("settlement", "location_complex"):
            self.assertTrue(is_settlement_map_site(system_location_type=key))
        self.assertTrue(uses_settlement_fine_footprint(system_location_type="district"))
        for key in ("district", "building", "room", "geographic", "city", None):
            with self.subTest(key=key):
                self.assertFalse(is_settlement_map_site(
                    system_location_type=key, system_location_subtype="city"))
        self.assertFalse(uses_settlement_fine_footprint(
            system_location_type="geographic", system_location_subtype="underground_city"))

    def test_custom_payload_types_select_pipeline_from_world_registry(self):
        registry = WorldLocationTypeRegistry.model_validate([
            {"system_type": "elven_city", "display_type": "City", "payload_kind": "settlement"},
            {"system_type": "custom_district", "display_type": "District", "payload_kind": "district"},
        ]).merged_with_engine()
        self.assertTrue(is_settlement_map_site(system_location_type="elven_city", registry=registry))
        self.assertTrue(uses_settlement_fine_footprint(system_location_type="custom_district", registry=registry))
        self.assertFalse(is_settlement_map_site(system_location_type="custom_district", registry=registry))
        self.assertTrue(is_district_location("custom_district", registry=registry))
        self.assertFalse(is_district_location("location_complex", registry=registry))
        pin = LocationsIndexPin(location_uid="custom", map_x=0, map_y=0,
                                system_location_type="elven_city")
        self.assertEqual(location_mark_pins([pin], registry=registry), [])

    def test_c6_and_packing_targets_respect_world_contract(self):
        world = World(world_uid="payload-world", name="World", created_at="2026-10-06",
                      location_type_registry=[{
                          "system_type": "elven_city", "display_type": "City", "payload_kind": "settlement",
                      }])
        base = NamedLocation(location_uid="complex", world_uid=world.world_uid,
                             display_name="Complex", system_location_type="location_complex",
                             created_at=world.created_at)
        custom = replace(base, location_uid="custom", system_location_type="elven_city")
        geographic = replace(base, location_uid="geography", system_location_type="geographic",
                             system_location_subtype="city")
        district = replace(base, location_uid="district", system_location_type="district")
        self.assertTrue(is_settlement_outdoor_target(base, world=world))
        self.assertTrue(is_settlement_outdoor_target(custom, world=world))
        self.assertFalse(is_settlement_outdoor_target(geographic, world=world))
        self.assertEqual(packing_targets([base, custom, geographic, district],
                                        frozenset({"complex", "custom", "geography", "district"}),
                                        world=world), [base, custom])

    def test_explicit_no_payload_disables_builtin_pipeline(self):
        registry = WorldLocationTypeRegistry.model_validate([{
            "system_type": "settlement", "display_type": "Generic", "payload_kind": None,
        }]).merged_with_engine()
        self.assertFalse(is_settlement_map_site(system_location_type="settlement", registry=registry))

    def test_custom_type_selects_builtin_contract(self):
        entry = LocationTypeEntry(system_type="elven_city", display_type="Elven city",
                                  payload_kind="settlement")
        payload = LocationPayload.validate(entry.payload_kind, {
            "system_city_size": "custom-size", "structure_counts": {"custom-plot": 2},
            "is_inhabited": False,
        })
        self.assertIsInstance(payload, SettlementPayload)
        self.assertEqual(payload.system_city_size, "custom-size")
        self.assertEqual(payload.plot_counts, {"custom-plot": 2})
        self.assertFalse(payload.is_inhabited)
        self.assertEqual(payload.model_dump(mode="json")["plot_counts"], {"custom-plot": 2})

    def test_invalid_kind_is_rejected(self):
        with self.assertRaises(ValidationError):
            LocationTypeEntry(system_type="custom", display_type="Custom",
                              payload_kind="unknown")
        with self.assertRaises(ValueError):
            LocationPayload.model_for("unknown")

    def test_generic_type_has_no_payload(self):
        entry = LocationTypeEntry(system_type="custom", display_type="Custom")
        self.assertIsNone(LocationPayload.validate(entry.payload_kind, None))
        with self.assertRaisesRegex(ValueError, "without payload_kind"):
            LocationPayload.validate(entry.payload_kind, {})

    def test_empty_settlement_uses_pojo_defaults(self):
        payload = LocationPayload.validate("settlement", None)
        self.assertTrue(payload.is_inhabited)
        self.assertIsNone(payload.system_city_size)
        self.assertIsNone(payload.settlement_density)
        with self.assertRaises(ValidationError):
            payload.is_inhabited = False

    def test_district_topology_is_typed_and_roundtrips(self):
        wire = {"district_topology": {
            "cell_x": 1, "cell_y": 2, "origin_x": 10, "origin_y": 20,
            "width_m": 30, "depth_m": 40, "ground_z": -2,
            "template_system_name": "custom-template", "slot_index": 0,
        }}
        payload = LocationPayload.validate("district", wire)
        self.assertIsInstance(payload, DistrictPayload)
        self.assertIsInstance(payload.district_topology, DistrictTopologySlot)
        self.assertEqual(payload.district_topology.width_fine, 30)
        self.assertEqual(DistrictPayload.model_validate_json(payload.model_dump_json()), payload)
        with self.assertRaises(ValidationError):
            LocationPayload.validate("district", {"district_topology": {"cell_x": 1}})

    def test_payload_fields_do_not_duplicate_legacy_cascade_channels(self):
        self.assertEqual(len(cascade_channels(SettlementPayload)), 3)
        self.assertNotIn("economic_tier", SettlementPayload.model_fields)
        self.assertNotIn("system_location_mood", SettlementPayload.model_fields)
        self.assertNotIn("is_inhabited", SettlementSkeleton.model_fields)
        skeleton = SettlementSkeleton.model_validate({"structure_counts": {"plot": 2}})
        self.assertEqual(skeleton.plot_counts, {"plot": 2})
        self.assertEqual(len(cascade_channels(SettlementSkeleton)), 1)

    def test_builtin_kinds_survive_minimal_fixture_and_merge(self):
        engine = WorldLocationTypeRegistry.canonical_engine()
        minimal = WorldLocationTypeRegistry.canonical_defaults()
        for key, kind in (("settlement", PayloadKind.SETTLEMENT),
                          ("location_complex", PayloadKind.SETTLEMENT),
                          ("district", PayloadKind.DISTRICT)):
            self.assertEqual(engine.entry_for(key).payload_kind, kind)
            self.assertEqual(minimal.entry_for(key).payload_kind, kind)
            self.assertEqual(minimal.merged_with_engine().entry_for(key).payload_kind, kind)
        self.assertIsNone(engine.entry_for("geographic").payload_kind)

    def test_world_overlay_preserves_missing_and_respects_explicit_kind(self):
        for wire, expected in (({}, PayloadKind.SETTLEMENT),
                               ({"payload_kind": None}, None),
                               ({"payload_kind": "district"}, PayloadKind.DISTRICT)):
            with self.subTest(wire=wire):
                world = WorldLocationTypeRegistry.model_validate([
                    {"system_type": "settlement", "display_type": "World", **wire},
                ])
                self.assertEqual(world.merged_with_engine().entry_for("settlement").payload_kind,
                                 expected)

    def test_complex_recipes_and_hierarchy(self):
        engine = WorldLocationTypeRegistry.canonical_engine()
        complex_type = engine.entry_for("location_complex")
        self.assertEqual({s.system_subtype for s in complex_type.subtypes},
                         {"crypt", "mine", "ruins", "fortress", "lair"})
        for recipe in complex_type.subtypes:
            self.assertFalse(recipe.is_inhabited)
            self.assertTrue(recipe.typical_district_types)
            self.assertEqual(set(recipe.footprint_by_size), {"small", "medium", "large"})
            self.assertTrue(all(v > 0 for v in recipe.footprint_by_size.values()))
        self.assertTrue(engine.allows_parent("district", "location_complex"))
        self.assertTrue(engine.allows_parent("building", "location_complex"))

    def test_complex_recipe_can_be_authored_as_inhabited(self):
        world = WorldLocationTypeRegistry.model_validate([{
            "system_type": "location_complex", "display_type": "Custom",
            "subtypes": [{"system_subtype": "ruins", "is_inhabited": True}],
        }])
        self.assertTrue(world.merged_with_engine().subtype_for("location_complex", "ruins").is_inhabited)
        minimal = WorldLocationTypeRegistry.model_validate([{
            "system_type": "location_complex", "display_type": "Custom",
            "subtypes": [{"system_subtype": "ruins"}],
        }])
        self.assertFalse(minimal.merged_with_engine().subtype_for("location_complex", "ruins").is_inhabited)


if __name__ == "__main__":
    unittest.main()
