"""Unit tests for jsonValidation Phase 2 — JV-2 index, refs, locations, connections."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.index.worldRegistryIndex import build_world_registry_index
from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.syntheticBundle import build_synthetic_bundle
from app.application.worldData.jsonValidation.types import SectionKey, ValidationKind, ValidationRequest


def _run(coro):
    return asyncio.run(coro)


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"


def _load_template() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


class TestWorldRegistryIndex(unittest.TestCase):

    def test_index_from_template(self):
        bundle = _load_template()
        index = build_world_registry_index(bundle["world"])
        self.assertTrue(index.has_ref(RefKind.LOC_TYPE, "region"))
        self.assertTrue(index.has_ref(RefKind.CONN, "lake_shoreline"))
        self.assertTrue(index.has_ref(RefKind.LORE, "terrain_plains"))
        self.assertTrue(index.has_ref(RefKind.TERRAIN, "plains"))
        self.assertTrue(index.has_ref(RefKind.CLIMATE, "cold"))


class TestJsonValidationJv2(unittest.TestCase):

    def test_world_template_bundle_ok(self):
        bundle = _load_template()
        facade = JsonValidationFacade()
        result = _run(facade.validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bundle,
        )))
        self.assertTrue(result.ok, [f"{i.path}: {i.message}" for i in result.issues])

    def test_unknown_location_type_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["locations"] = [{
            "location_uid": "loc-bad",
            "display_name": "Bad",
            "system_location_type": "not_a_type",
            "created_at": "2026-01-01T00:00:00Z",
        }]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any("system_location_type" in i.path for i in result.issues))

    def test_broken_edge_node_fk(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["connection_edges"] = [{
            "edge_uid": "ce-bad",
            "from_node_uid": "missing-a",
            "to_node_uid": "missing-b",
            "connection_type": "trail",
            "graph_level": "world",
        }]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.code == "BROKEN_FK" for i in result.issues))

    def test_geographic_lake_without_declare_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["connection_nodes"] = []
        bad["connection_edges"] = []
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.code == "MISSING_DECLARE" for i in result.issues))

    def test_synthetic_section_locations(self):
        bundle = _load_template()
        world = bundle["world"]
        one_location = [bundle["locations"][0]]
        synthetic = build_synthetic_bundle(world, SectionKey.LOCATIONS, one_location)
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.SECTION,
            payload=synthetic,
            section=SectionKey.LOCATIONS,
            world_uid=world["world_uid"],
        )))
        self.assertTrue(result.ok, result.issues)

    def test_climate_pole_limit(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["locations"] = list(bad["locations"]) + [
            {
                "location_uid": "pole-1",
                "display_name": "Pole 1",
                "system_location_type": "climate_pole",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "location_uid": "pole-2",
                "display_name": "Pole 2",
                "system_location_type": "climate_pole",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.code == "CLIMATE_POLE_LIMIT" for i in result.issues))


if __name__ == "__main__":
    unittest.main()
