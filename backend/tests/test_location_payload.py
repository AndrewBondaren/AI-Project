"""P1 typed payload contract — tz_locations §Payload per type."""

import json
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
from app.dataModel.locations.namedLocation import BundleNamedLocation
from app.dataModel.locations.locationType.locationTypeSubtypeEntry import LocationTypeSubtypeEntry
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.worldRow import location_types


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
        self.assertFalse(payload.is_inhabited)
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

    def test_uninhabited_payload_rejects_specializations(self):
        with self.assertRaisesRegex(ValidationError, "requires is_inhabited=true"):
            SettlementPayload.model_validate({
                "is_inhabited": False, "system_settlement_specializations": ["extract"],
            })
        for binds in (None, []):
            with self.subTest(binds=binds):
                payload = SettlementPayload.model_validate({
                    "is_inhabited": False, "system_settlement_specializations": binds,
                })
                self.assertFalse(payload.is_inhabited)
        inhabited = SettlementPayload.model_validate({
            "is_inhabited": True, "system_settlement_specializations": ["extract"],
        })
        self.assertTrue(inhabited.is_inhabited)

    def test_payload_fields_do_not_duplicate_legacy_cascade_channels(self):
        self.assertEqual(len(cascade_channels(SettlementPayload)), 3)
        self.assertNotIn("economic_tier", SettlementPayload.model_fields)
        self.assertNotIn("system_location_mood", SettlementPayload.model_fields)
        self.assertFalse(SettlementSkeleton().is_inhabited)
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
        self.assertTrue(engine.entry_for("settlement").is_inhabited)
        self.assertTrue(minimal.merged_with_engine().entry_for("settlement").is_inhabited)
        self.assertFalse(engine.entry_for("location_complex").is_inhabited)

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

    def test_recipe_overlay_survives_world_json_roundtrip(self):
        engine = WorldLocationTypeRegistry.canonical_engine().subtype_for("settlement", "city")
        for districts in (None, [], ["civic"]):
            for structures in (None, [], ["custom_structure"]):
                with self.subTest(districts=districts, structures=structures):
                    subtype = {
                        "system_subtype": "city", "l0_map_symbol": "u",
                        "footprint_by_size": {"huge": 8.0},
                    }
                    if districts is not None:
                        subtype["typical_district_types"] = districts
                    if structures is not None:
                        subtype["required_structure_types"] = structures
                    normalized = normalize_world({"location_type_registry": [{
                        "system_type": "settlement", "display_type": "Settlement",
                        "payload_kind": "settlement", "subtypes": [subtype],
                    }]}, partial=True)
                    stored = json.loads(json.dumps(normalized))
                    stored_subtype = stored["location_type_registry"][0]["subtypes"][0]
                    self.assertEqual("typical_district_types" in stored_subtype, districts is not None)
                    self.assertEqual("required_structure_types" in stored_subtype, structures is not None)
                    world = World(world_uid="recipe-world", name="World",
                                  created_at="2026-10-07", **stored)
                    recipe = location_types(world).subtype_for("settlement", "city")
                    self.assertEqual(recipe.typical_district_types,
                                     engine.typical_district_types if districts is None else districts)
                    self.assertEqual(recipe.required_structure_types,
                                     engine.required_structure_types if structures is None else structures)
                    self.assertEqual(recipe.footprint_by_size,
                                     {**engine.footprint_by_size, "huge": 8.0})

    def test_subtype_symbol_survives_world_json_roundtrip(self):
        engine = WorldLocationTypeRegistry.canonical_engine().subtype_for("settlement", "city")
        for override, expected in (({}, engine.l0_map_symbol),
                                   ({"l0_map_symbol": None}, engine.l0_map_symbol),
                                   ({"l0_map_symbol": "Ж"}, "Ж")):
            with self.subTest(override=override):
                normalized = normalize_world({"location_type_registry": [{
                    "system_type": "settlement", "display_type": "Settlement",
                    "payload_kind": "settlement", "subtypes": [{
                        "system_subtype": "city", "footprint_by_size": {"huge": 8.0},
                        **override,
                    }],
                }]}, partial=True)
                world = World(world_uid="symbol-world", name="World",
                              created_at="2026-10-07", **json.loads(json.dumps(normalized)))
                recipe = location_types(world).subtype_for("settlement", "city")
                self.assertEqual(recipe.l0_map_symbol, expected)
                self.assertEqual(recipe.typical_district_types, engine.typical_district_types)
                self.assertEqual(recipe.required_structure_types, engine.required_structure_types)
                self.assertEqual(recipe.footprint_by_size, {**engine.footprint_by_size, "huge": 8.0})

    def test_subtype_symbol_constraints_apply_only_to_strings(self):
        self.assertIsNone(LocationTypeSubtypeEntry.model_validate({
            "system_subtype": "custom", "l0_map_symbol": None,
        }).l0_map_symbol)
        for invalid in ("", "ab"):
            with self.subTest(symbol=invalid), self.assertRaises(ValidationError):
                LocationTypeSubtypeEntry.model_validate({
                    "system_subtype": "custom", "l0_map_symbol": invalid,
                })

    def test_settlement_allows_root_territory_and_region(self):
        for registry in (WorldLocationTypeRegistry.canonical_engine(),
                         WorldLocationTypeRegistry.canonical_defaults().merged_with_engine()):
            for parent in (None, "territory", "region"):
                with self.subTest(parent=parent):
                    self.assertTrue(registry.allows_parent("settlement", parent))
            self.assertFalse(registry.allows_parent("settlement", "building"))

    def test_settlement_parent_overlay_survives_world_json_roundtrip(self):
        for override, expected in (({}, [None, "territory", "region"]),
                                   ({"parent_types": []}, [None, "territory", "region"]),
                                   ({"parent_types": ["region"]}, ["region"]),
                                   ({"parent_types": [None]}, [None])):
            with self.subTest(override=override):
                normalized = normalize_world({"location_type_registry": [{
                    "system_type": "settlement", "display_type": "Settlement", **override,
                }]}, partial=True)
                world = World(world_uid="parents-world", name="World",
                              created_at="2026-10-07", **json.loads(json.dumps(normalized)))
                registry = location_types(world)
                self.assertEqual(registry.entry_for("settlement").parent_types, expected)
                for parent in (None, "territory", "region", "building"):
                    self.assertEqual(registry.allows_parent("settlement", parent), parent in expected)

    def test_complex_recipes_and_hierarchy(self):
        engine = WorldLocationTypeRegistry.canonical_engine()
        complex_type = engine.entry_for("location_complex")
        self.assertEqual({s.system_subtype for s in complex_type.subtypes},
                         {"crypt", "mine", "ruins", "fortress", "lair"})
        for recipe in complex_type.subtypes:
            self.assertIsNone(recipe.is_inhabited)
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
        self.assertIsNone(minimal.merged_with_engine().subtype_for("location_complex", "ruins").is_inhabited)

    def test_instance_defaults_come_from_type_even_without_subtype(self):
        for kind, subtype, expected in (
            ("settlement", None, True), ("settlement", "city", True),
            ("settlement", "unknown", True), ("location_complex", None, False),
            ("location_complex", "ruins", False),
        ):
            with self.subTest(kind=kind, subtype=subtype):
                row = BundleNamedLocation.model_validate({
                    "location_uid": "instance", "display_name": "Instance",
                    "system_location_type": kind, "system_location_subtype": subtype,
                })
                self.assertIs(row.location_payload.is_inhabited, expected)

    def test_type_subtype_instance_priority_preserves_explicit_false(self):
        for type_flag in (False, True):
            for subtype_flag in (None, False, True):
                registry = WorldLocationTypeRegistry.model_validate([{
                    "system_type": "custom_site", "display_type": "Site", "payload_kind": "settlement",
                    "is_inhabited": type_flag,
                    "subtypes": [{"system_subtype": "custom", "is_inhabited": subtype_flag}],
                }])
                for instance_flag in (None, False, True):
                    with self.subTest(type=type_flag, subtype=subtype_flag, instance=instance_flag):
                        wire = {"location_uid": "instance", "display_name": "Instance",
                                "system_location_type": "custom_site", "system_location_subtype": "custom"}
                        if instance_flag is not None:
                            wire["location_payload"] = {"is_inhabited": instance_flag}
                        row = BundleNamedLocation.model_validate(wire, context={"location_type_registry": registry})
                        expected = (instance_flag if instance_flag is not None else
                                    subtype_flag if subtype_flag is not None else type_flag)
                        self.assertIs(row.location_payload.is_inhabited, expected)

    def test_custom_type_defaults_false_and_null_instance_is_invalid(self):
        registry = WorldLocationTypeRegistry.model_validate([{
            "system_type": "custom_site", "display_type": "Site", "payload_kind": "settlement",
        }])
        wire = {"location_uid": "instance", "display_name": "Instance", "system_location_type": "custom_site"}
        row = BundleNamedLocation.model_validate(wire, context={"location_type_registry": registry})
        self.assertFalse(row.location_payload.is_inhabited)
        for override in ({"is_inhabited": None}, {"location_payload": {"is_inhabited": None}}):
            with self.subTest(override=override), self.assertRaises(ValidationError):
                BundleNamedLocation.model_validate({**wire, **override}, context={"location_type_registry": registry})

    def test_override_serialization_keeps_omission_false_and_null_distinct(self):
        bare_type = LocationTypeEntry(system_type="settlement", display_type="Settlement")
        bare_subtype = LocationTypeSubtypeEntry(system_subtype="city")
        self.assertNotIn("is_inhabited", bare_type.model_dump(mode="json"))
        self.assertNotIn("is_inhabited", bare_subtype.model_dump(mode="json"))
        self.assertIs(LocationTypeEntry.model_validate({
            **bare_type.model_dump(), "is_inhabited": False,
        }).model_dump()["is_inhabited"], False)
        self.assertIsNone(LocationTypeSubtypeEntry.model_validate({
            "system_subtype": "city", "is_inhabited": None,
        }).model_dump()["is_inhabited"])

    def test_world_normalization_roundtrip_preserves_default_and_overrides(self):
        for kind, type_override, subtype_override, expected in (
            ("settlement", {}, {}, True),
            ("settlement", {"is_inhabited": False}, {}, False),
            ("settlement", {}, {"is_inhabited": False}, False),
            ("settlement", {}, {"is_inhabited": None}, True),
            ("location_complex", {"is_inhabited": True}, {}, True),
            ("location_complex", {}, {"is_inhabited": True}, True),
        ):
            with self.subTest(kind=kind, type=type_override, subtype=subtype_override):
                subtype = "city" if kind == "settlement" else "ruins"
                normalized = normalize_world({"location_type_registry": [{
                    "system_type": kind, "display_type": "Site", "payload_kind": "settlement",
                    **type_override, "subtypes": [{"system_subtype": subtype, "l0_map_symbol": "u",
                                                   **subtype_override}],
                }]}, partial=True)
                world = World(world_uid="w", name="World", created_at="2026-10-07", **normalized)
                row = BundleNamedLocation.model_validate({
                    "location_uid": "instance", "display_name": "Instance",
                    "system_location_type": kind, "system_location_subtype": subtype,
                }, context={"location_type_registry": location_types(world)})
                self.assertIs(row.location_payload.is_inhabited, expected)


if __name__ == "__main__":
    unittest.main()
