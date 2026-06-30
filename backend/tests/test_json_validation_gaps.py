"""Unit tests for jsonValidation gap closure — JV-1/2 registry enums, cross-row, T2."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.normalize.worldRegistries import (
    normalize_location_type_registry,
)
from app.application.worldData.jsonValidation.types import SectionKey, ValidationKind, ValidationRequest
from app.application.worldData.jsonValidation.validators.connectionEdgeRow import (
    collect_hydrology_turn_issues,
)
from app.application.worldData.jsonValidation.validators.registryRefs import (
    _collect_registry_ref_issues,
)
from app.application.worldData.jsonValidation.index.worldRegistryIndex import build_world_registry_index
from app.application.worldData.jsonValidation.syntheticBundle import build_synthetic_bundle


def _run(coro):
    return asyncio.run(coro)


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"


def _load_template() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


class TestJsonValidationGaps(unittest.TestCase):

    def test_world_template_still_ok(self):
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=_load_template(),
        )))
        self.assertTrue(result.ok, [f"{i.path}: {i.message}" for i in result.issues])

    def test_material_category_e03_invalid_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["world"]["material_registry"][0]["material_category"] = "plasma"
        index = build_world_registry_index(bad["world"])
        issues = _collect_registry_ref_issues(bad["world"], index)
        self.assertTrue(any("material_category" in i.path for i in issues))

    def test_location_type_registry_normalized_to_array(self):
        world = {"location_type_registry": {"region": {"display_name": "Region"}}}
        normalize_location_type_registry(world)
        self.assertIsInstance(world["location_type_registry"], list)
        self.assertEqual(world["location_type_registry"][0]["system_type"], "region")
        self.assertEqual(world["location_type_registry"][0]["display_type"], "Region")

    def test_city_size_radius_alias(self):
        bundle = _load_template()
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bundle,
        )))
        town = next(
            r for r in result.normalized["world"]["city_size_registry"]
            if r["system_size"] == "town"
        )
        self.assertEqual(town.get("map_cells_count"), 1)

    def test_parent_types_rule(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["world"]["location_type_registry"] = [{
            "system_type": "room",
            "display_type": "Room",
            "parent_types": ["building"],
        }]
        bad["locations"] = [
            {
                "location_uid": "b1",
                "display_name": "Hall",
                "system_location_type": "building",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "location_uid": "r1",
                "display_name": "Room",
                "system_location_type": "room",
                "parent_location_uid": "b1",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "location_uid": "bad-child",
                "display_name": "Bad",
                "system_location_type": "room",
                "parent_location_uid": "r1",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.code == "INVALID_PARENT_TYPE" for i in result.issues))

    def test_room_requires_building_ancestor(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["locations"] = [{
            "location_uid": "r1",
            "display_name": "Room",
            "system_location_type": "room",
            "created_at": "2026-01-01T00:00:00Z",
        }]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.code == "MISSING_BUILDING_ANCESTOR" for i in result.issues))

    def test_river_turn_over_45_fails(self):
        coords = {
            "a": (0, 0),
            "b": (100, 0),
            "c": (100, 100),
        }
        edges = [{
            "edge_uid": "e1",
            "from_node_uid": "a",
            "to_node_uid": "b",
            "connection_type": "river",
        }, {
            "edge_uid": "e2",
            "from_node_uid": "b",
            "to_node_uid": "c",
            "connection_type": "river",
        }]
        issues = collect_hydrology_turn_issues(edges, coords)
        self.assertTrue(any(i.code == "RIVER_TURN" for i in issues))

    def test_synthetic_section_locations_ok(self):
        bundle = _load_template()
        world = bundle["world"]
        payload = [bundle["locations"][0]]
        synthetic = build_synthetic_bundle(world, SectionKey.LOCATIONS, payload)
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.SECTION,
            payload=synthetic,
            section=SectionKey.LOCATIONS,
            world_uid=world["world_uid"],
        )))
        self.assertTrue(result.ok, result.issues)


if __name__ == "__main__":
    unittest.main()
