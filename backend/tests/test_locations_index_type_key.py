"""Step 6: typed pin identity, world-aware new indexes, historical snapshots."""

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from pydantic import ValidationError

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError, validate_contracts
from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.application.jsonValidation.sourceValidation import registry_vocabulary, validate_reference_value
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.structureGeneratorService import _room_to_named_location
from app.application.worldData.pack.bake.locationsIndexBake import build_locations_index
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationsIndexRead import load_locations_index
from app.application.worldData.render.pack.locationPinOverlay import overlay_location_pins
from app.dataModel.annotationPolicy import WireFieldPolicy, field_policy
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    LocationTypeKey, WorldLocationTypeRegistry,
)
from app.dataModel.locations.locationType.locationTypeEntry import LocationTypeEntry
from app.dataModel.locations.namedLocation.bundleNamedLocation import BundleNamedLocation
from app.dataModel.registryKey import RegistryKey, registry_key_target
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.db.models.locationLevel import LocationLevel
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class LocationsIndexTypeKeyTests(unittest.TestCase):
    def location(self, key="building"):
        return NamedLocation(
            location_uid="loc", world_uid="world", display_name="Place",
            system_location_type=key, created_at="2026-10-18",
            map_x=1, map_y=2,
        )

    def test_alias_policy_and_json_round_trip(self):
        annotation = LocationsIndexPin.model_fields["system_location_type"].annotation
        self.assertIs(registry_key_target(annotation), WorldLocationTypeRegistry)
        self.assertIs(registry_key_target(LocationTypeKey), WorldLocationTypeRegistry)
        self.assertEqual(field_policy(annotation), WireFieldPolicy.DEFAULT_WHEN_MISSING)
        pin = LocationsIndexPin(location_uid="loc", map_x=1, map_y=2,
                                system_location_type="building")
        self.assertIsInstance(pin.system_location_type, RegistryKey)
        wire = json.loads(pin.model_dump_json())
        self.assertIs(type(wire["system_location_type"]), str)
        self.assertEqual(wire["system_location_type"], "building")
        self.assertEqual(LocationsIndexPin.model_validate(wire), pin)

    def test_historical_missing_null_and_removed_type_remain_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = WorldPackPaths(pack_root=Path(directory), world_uid="world")
            wire = {"locations": [
                {"location_uid": "missing", "map_x": 0, "map_y": 0},
                {"location_uid": "null", "map_x": 1, "map_y": 1, "system_location_type": None},
                {"location_uid": "old", "map_x": 2, "map_y": 2,
                 "system_location_type": "removed-world-type", "legacy_extra": True},
            ]}
            paths.locations_index_path().write_text(json.dumps(wire), encoding="utf-8")
            index = load_locations_index(paths)
            self.assertIsNone(index.locations[0].system_location_type)
            self.assertIsNone(index.locations[1].system_location_type)
            self.assertEqual(index.locations[2].system_location_type, "removed-world-type")
            self.assertIsInstance(index.locations[2].system_location_type, RegistryKey)
            self.assertEqual(LocationsIndexWire.model_validate_json(index.model_dump_json()), index)

    def test_new_index_validates_world_keys_and_rejects_unknown(self):
        world = World(world_uid="world", name="World", created_at="now",
                      location_type_registry=[{"system_type": "custom-landmark", "display_type": "Custom"}])
        index = build_locations_index([self.location("custom-landmark")], world)
        self.assertEqual(index.locations[0].system_location_type, "custom-landmark")
        self.assertIsInstance(index.locations[0].system_location_type, RegistryKey)
        with self.assertRaises(UnresolvedModelError) as caught:
            build_locations_index([self.location("absent-type")], world)
        self.assertEqual(caught.exception.issues[0].code, "REF_W_UNKNOWN")
        self.assertEqual(caught.exception.issues[0].path,
                         ("locations_index", "locations", 0, "system_location_type"))

    def test_worldless_builder_accepts_engine_key_and_rejects_unknown(self):
        location = self.location()
        index = build_locations_index([location])
        self.assertEqual(index.locations[0].system_location_type, location.system_location_type)
        with self.assertRaises(UnresolvedModelError):
            build_locations_index([replace(location, system_location_type="unknown")])

    def test_invalid_key_wire_is_rejected(self):
        for value in ("", 1, {}, []):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                LocationsIndexPin(location_uid="loc", map_x=0, map_y=0,
                                  system_location_type=value)

    def test_writer_reader_preserve_json_shape_and_custom_world_key(self):
        world = World(world_uid="world", name="World", created_at="now",
                      location_type_registry=[{"system_type": "custom-landmark", "display_type": "Custom"}])
        index = build_locations_index([self.location("custom-landmark")], world)
        with tempfile.TemporaryDirectory() as directory:
            paths = WorldPackPaths(pack_root=Path(directory), world_uid="world")
            writer = WorldPackWriter(paths)
            path = writer.write_locations_index(index)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {
                "locations": [{"location_uid": "loc", "map_x": 1, "map_y": 2,
                               "map_z": 0, "display_name": "Place",
                               "system_location_type": "custom-landmark",
                               "system_location_subtype": None, "system_city_size": None}],
            })
            self.assertEqual(load_locations_index(paths), index)

    def test_sql_overlay_keeps_nominal_key_without_live_membership(self):
        index = LocationsIndexWire(locations=[
            LocationsIndexPin(location_uid="loc", map_x=1, map_y=2,
                              system_location_type="old-snapshot-type"),
        ])
        location = self.location("another-historical-type")
        overlaid = overlay_location_pins(index, [location])
        key = overlaid.locations[0].system_location_type
        self.assertIsInstance(key, RegistryKey)
        self.assertEqual(key, location.system_location_type)
        self.assertIs(type(location.system_location_type), str)
        self.assertEqual(index.locations[0].system_location_type, "old-snapshot-type")

    def test_generated_room_uses_registry_constant_and_preserves_sql_value(self):
        room = _RoomInstance(
            room_id="room", instance_idx=0, z_offset=0, shape_type="rectangle",
            width=2, depth=2, z_height=3, display_name="Room", room_type="bedroom",
            is_public=False, is_forbidden=False, required=True,
            wall_material="wood", floor_material="wood", origin_x=4, origin_y=5,
        )
        level = LocationLevel("level", "building", 10, 3, "Floor")
        location = _room_to_named_location(room, self.location(), level, "room-uid")
        self.assertEqual(location.system_location_type, WorldLocationTypeRegistry.SYSTEM_TYPE_ROOM)
        self.assertEqual(location.system_location_type, "room")
        self.assertIsNotNone(WorldLocationTypeRegistry.canonical_engine().entry_for(location.system_location_type))
        self.assertEqual(location.system_location_subtype, room.room_type)

    def test_registry_self_key_and_parent_keys_are_typed_and_keep_wire(self):
        wire = {"system_type": "custom-place", "display_type": "Место",
                "parent_types": [None, "another-custom-place"]}
        entry = LocationTypeEntry.model_validate(wire)
        self.assertIsInstance(entry.system_type, RegistryKey)
        self.assertIsInstance(entry.parent_types[1], RegistryKey)
        self.assertIsNone(entry.parent_types[0])
        self.assertIs(type(entry.display_type), str)
        for name in ("system_type", "parent_types"):
            self.assertIs(registry_key_target(LocationTypeEntry.model_fields[name].annotation),
                          WorldLocationTypeRegistry)
        self.assertEqual(entry.model_dump(mode="json"), {
            **wire, "subtypes": [],
        })
        self.assertEqual(LocationTypeEntry.model_validate_json(entry.model_dump_json()), entry)
        self.assertEqual(entry.fixture_identity().system_type, entry.system_type)

    def test_registry_canonical_and_overlay_rows_keep_typed_family(self):
        for registry in (WorldLocationTypeRegistry.canonical_defaults(),
                         WorldLocationTypeRegistry.canonical_engine(),
                         WorldLocationTypeRegistry.model_validate([
                             {"system_type": "custom-place", "display_type": "Custom",
                              "parent_types": ["building"]},
                         ]).merged_with_engine()):
            for entry in registry.root:
                self.assertIsInstance(entry.system_type, RegistryKey)
                self.assertTrue(all(parent is None or isinstance(parent, RegistryKey)
                                    for parent in entry.parent_types))
            self.assertEqual(WorldLocationTypeRegistry.model_validate_json(registry.model_dump_json()), registry)

    def test_bundle_identity_key_is_typed_and_db_wire_remains_plain_string(self):
        registry = WorldLocationTypeRegistry.model_validate([
            {"system_type": "custom-settlement", "display_type": "Custom",
             "payload_kind": "settlement", "is_inhabited": True},
        ])
        bundle = BundleNamedLocation.model_validate({
            "location_uid": "custom", "display_name": "Custom",
            "system_location_type": "custom-settlement", "plot_counts": {"home": 2},
        }, context={"location_type_registry": registry})
        self.assertIs(registry_key_target(BundleNamedLocation.model_fields["system_location_type"].annotation),
                      WorldLocationTypeRegistry)
        self.assertIsInstance(bundle.system_location_type, RegistryKey)
        self.assertTrue(bundle.location_payload.is_inhabited)
        self.assertEqual(bundle.location_payload.plot_counts, {"home": 2})
        db_fields = bundle.to_db_fields()
        self.assertIs(type(db_fields["system_location_type"]), str)
        restored = BundleNamedLocation.model_validate(db_fields, context={"location_type_registry": registry})
        self.assertEqual(restored, bundle)

    def test_family_rejects_empty_and_nonstring_keys_without_live_membership(self):
        for key in ("", 7, {}):
            with self.subTest(key=key):
                with self.assertRaises(ValidationError):
                    LocationTypeEntry(system_type=key, display_type="Custom")
                with self.assertRaises(ValidationError):
                    LocationTypeEntry(system_type="custom", display_type="Custom", parent_types=[key])
                with self.assertRaises(ValidationError):
                    BundleNamedLocation(location_uid="loc", display_name="Custom", system_location_type=key)

    def test_parent_reference_lists_never_become_ref_w_identity_keys(self):
        world = World(world_uid="world", name="World", created_at="now",
                      location_type_registry=[{"system_type": "custom-place", "display_type": "Custom",
                                               "parent_types": ["building"]}])
        ctx = ResolveContext(path_prefix=("locations", "system_location_type"), validate_only=True)
        vocabulary = registry_vocabulary(world, WorldLocationTypeRegistry, ctx, ctx.path_prefix)
        self.assertIn("custom-place", vocabulary)
        self.assertNotIn("['building']", vocabulary)
        validate_reference_value(world, LocationTypeKey, "custom-place", ctx, ctx.path_prefix)
        with self.assertRaises(UnresolvedModelError) as caught:
            validate_reference_value(world, LocationTypeKey, "['building']", ctx, ctx.path_prefix)
        self.assertEqual(caught.exception.issues[0].code, "REF_W_UNKNOWN")

    def test_parent_key_membership_accepts_null_and_rejects_unknown(self):
        ctx = ResolveContext(validate_only=True)
        references = WorldRegistryIndex(registry_vocabularies={
            WorldLocationTypeRegistry: frozenset({"custom-place", "building"}),
        })
        wire = {"system_type": "custom-place", "display_type": "Custom",
                "parent_types": [None, "building"]}
        validate_contracts(LocationTypeEntry, wire, ctx=ctx, references=references)
        annotation = LocationTypeEntry.model_fields["parent_types"].annotation
        validate_reference_value(None, annotation, [None, "building"], ctx, ("parent_types",), references)
        with self.assertRaises(UnresolvedModelError) as caught:
            validate_contracts(LocationTypeEntry, {**wire, "parent_types": [None, "unknown"]},
                               ctx=ctx, references=references)
        self.assertEqual(caught.exception.issues[0].path, ("parent_types", 1))
        self.assertEqual(caught.exception.issues[0].code, "REF_W_UNKNOWN")
        with self.assertRaises(UnresolvedModelError):
            validate_reference_value(None, annotation, [None, "unknown"], ctx, ("parent_types",), references)

    def test_bundle_reference_boundary_rejects_unknown_type(self):
        ctx = ResolveContext(validate_only=True)
        references = WorldRegistryIndex(registry_vocabularies={
            WorldLocationTypeRegistry: frozenset({"custom-place"}),
        })
        wire = {"location_uid": "loc", "display_name": "Custom", "system_location_type": "custom-place"}
        validate_contracts(BundleNamedLocation, wire, ctx=ctx, references=references)
        with self.assertRaises(UnresolvedModelError) as caught:
            validate_contracts(BundleNamedLocation, {**wire, "system_location_type": "unknown"},
                               ctx=ctx, references=references)
        self.assertEqual(caught.exception.issues[0].path, ("system_location_type",))


if __name__ == "__main__":
    unittest.main()
