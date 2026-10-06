"""K1 interior transition wire and settlement frame round trips, without production cutover."""

import copy
import unittest

from app.application.worldData.pack.io.packBlobWire import (
    InteriorTransitionsRebuildRequired, append_settlement_structure_district,
    encode_settlement_structure_frames, parse_building_interior_transitions_blob,
    parse_settlement_structure_blob, parse_settlement_structure_payload,
    settlement_structure_payload, write_settlement_structure_blob,
)
from app.application.worldData.pack.io.tileCodec import PAYLOAD_KIND_SETTLEMENT_STRUCTURE, TileCodec
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.dataModel.worldPack.settlementStructureWire import BuildingInteriorTransitionsWire, SettlementStructureWire


class TransitionPackWireTest(unittest.TestCase):
    def setUp(self):
        self.codec = TileCodec()
        self.registry = WorldTransitionTypeRegistry.model_validate([
            {"system_type": "custom_gate", "display_name": "Gate", "behaves_as": "gate"},
            *WorldTransitionTypeRegistry.canonical_engine().model_dump(mode="json"),
        ])
        self.transition = {
            "transition_uid": "stable-uid", "world_uid": "world", "system_transition_type": "custom_gate",
            "source": {"space": "level", "level_uid": "floor", "host_location_uid": "house",
                       "node_uid": "graph-node", "x": 2, "y": 3, "z": 5},
            "destination": {"space": "level", "level_uid": "floor", "x": 3, "y": 3, "z": 5},
            "source_side": {"owner_location_uid": "room-1", "is_discovered": False,
                            "is_accessible": False, "entry_difficulty_override": 0,
                            "guard_level_override": 100, "display_name": "Inside"},
            "destination_side": {"owner_location_uid": "room-2", "entry_difficulty_override": None},
            "origin": "authored", "is_active": False, "is_bidirectional": True,
            "access_mechanic": ["key"], "type_params": {"width_cells": 2},
            "display_name": "Gate", "glossary_ref": "glossary-gate", "tag_refs": ["tag"],
        }
        self.interior_transitions = {"format": "building-interior-transitions-v1", "world_uid": "world",
                         "level_uids": ["floor"], "transitions": [self.transition]}

    def wire(self, *, interior_transitions=True, district="district", building="house"):
        payload = {"settlement_uid": "settlement", "districts": [{
            "location_uid": district, "areas": [{"area_uid": "area",
                "slot": {"ground_z": 5, "facing": "north"}, "buildings": [{
                    "location_uid": building, "shell_cells": [{"x": 1, "y": 2, "z": 5}],
                    **({"interior_transitions": self.interior_transitions} if interior_transitions else {}),
                }]}],
        }]}
        return parse_settlement_structure_payload(payload, registry=self.registry)

    def test_all_fields_and_references_round_trip_both_blob_encodings(self):
        wire = self.wire()
        for blob in (
            encode_settlement_structure_frames(wire, self.codec),
            self.codec.encode(PAYLOAD_KIND_SETTLEMENT_STRUCTURE, settlement_structure_payload(wire)),
        ):
            with self.subTest(framed=blob[2:6] == b"SSF1"):
                loaded = parse_settlement_structure_blob(blob, self.codec, registry=self.registry)
                self.assertEqual(loaded.model_dump(mode="json"), wire.model_dump(mode="json"))
                building = parse_building_interior_transitions_blob(blob, self.codec, building_uid="house", registry=self.registry)
                item = building.interior_transitions.transitions[0]
                self.assertEqual(item.transition_uid, "stable-uid")
                self.assertEqual(item.source.node_uid, "graph-node")
                self.assertEqual(item.destination_side.owner_location_uid, "room-2")
                self.assertEqual(item.source_side.entry_difficulty_override, 0)
                self.assertIsNone(item.destination_side.entry_difficulty_override)
                self.assertEqual(item.type_params.width_cells, 2)
                self.assertEqual(len(building.shell_cells), 1)

    def test_legacy_building_reads_as_shell_and_interior_requires_rebuild(self):
        wire = self.wire(interior_transitions=False)
        for blob in (encode_settlement_structure_frames(wire, self.codec),
                     self.codec.encode(PAYLOAD_KIND_SETTLEMENT_STRUCTURE, settlement_structure_payload(wire))):
            self.assertEqual(parse_settlement_structure_blob(blob, self.codec), wire)
            with self.assertRaisesRegex(InteriorTransitionsRebuildRequired, "rebuild"):
                parse_building_interior_transitions_blob(blob, self.codec, building_uid="house", registry=self.registry)
        with self.assertRaises(KeyError):
            parse_building_interior_transitions_blob(blob, self.codec, building_uid="absent", registry=self.registry)

    def validate(self, payload):
        return BuildingInteriorTransitionsWire.model_validate(payload, context={"transition_type_registry": self.registry})

    def test_marker_and_required_fields_prevent_silent_empty_interior(self):
        for field in BuildingInteriorTransitionsWire.model_fields:
            bad = copy.deepcopy(self.interior_transitions)
            del bad[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(bad)
        with self.assertRaises(ValueError):
            self.validate({**self.interior_transitions, "format": "building-interior-transitions-v0"})
        self.assertEqual(self.validate({**self.interior_transitions, "transitions": []}).transitions, [])

    def test_exterior_runtime_directional_and_out_of_scope_are_rejected(self):
        cases = [
            {"source": {"x": 2, "y": 3, "z": 5}},
            {"origin": "runtime"},
            {"world_uid": "other"},
            {"destination": {"space": "level", "level_uid": "outside", "x": 3, "y": 3, "z": 5}},
            {"system_transition_type": "fall", "is_bidirectional": False, "type_params": {}},
            {"system_transition_type": "portal", "type_params": {}},
        ]
        for patch in cases:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.validate({**self.interior_transitions, "transitions": [{**self.transition, **patch}]})

    def test_duplicate_uids_invalid_params_and_unknown_custom_type(self):
        for bad in (
            {**self.interior_transitions, "level_uids": ["floor", "floor"]},
            {**self.interior_transitions, "transitions": [self.transition, self.transition]},
            {**self.interior_transitions, "transitions": [{**self.transition, "type_params": {"width_cells": 0}}]},
        ):
            with self.assertRaises(ValueError):
                self.validate(bad)
        blob = encode_settlement_structure_frames(self.wire(), self.codec)
        with self.assertRaises(ValueError):
            parse_settlement_structure_blob(blob, self.codec)

    def test_append_preserves_existing_frames_and_mixed_shell_buildings(self):
        first = encode_settlement_structure_frames(self.wire(), self.codec)
        second = append_settlement_structure_district(
            first, self.wire(interior_transitions=False, district="other", building="shell").districts[0], self.codec)
        self.assertTrue(second.startswith(first))
        building = parse_building_interior_transitions_blob(second, self.codec, building_uid="house", registry=self.registry)
        self.assertEqual(building.interior_transitions.transitions[0].transition_uid, "stable-uid")
        with self.assertRaises(InteriorTransitionsRebuildRequired):
            parse_building_interior_transitions_blob(second, self.codec, building_uid="shell", registry=self.registry)
        with self.assertRaises(ValueError):
            parse_settlement_structure_blob(second[:-1], self.codec, registry=self.registry)

    def test_unframed_interior_rewrite_retains_custom_registry_and_old_district(self):
        first = self.codec.encode(PAYLOAD_KIND_SETTLEMENT_STRUCTURE, settlement_structure_payload(self.wire()))
        second = write_settlement_structure_blob(
            self.wire(interior_transitions=False, district="other", building="shell"), existing=first,
            codec=self.codec, registry=self.registry,
        )
        restored = parse_settlement_structure_blob(second, self.codec, registry=self.registry)
        self.assertEqual([item.location_uid for item in restored.districts], ["district", "other"])
        self.assertEqual(restored.districts[0].areas[0].buildings[0].interior_transitions.transitions[0].transition_uid,
                         "stable-uid")
