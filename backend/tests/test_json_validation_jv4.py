"""Unit tests for jsonValidation Phase 4 — JV-4/JV-5 building/district/barrier templates."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.generators.assemblers.settlementAssembler.planner.barrierDefaults import (
    DEFAULT_BARRIER_TEMPLATES,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    DEFAULT_BUILDING_TEMPLATES,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.defaults import (
    DEFAULT_DISTRICT_TEMPLATES,
)
from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.types import ValidationKind, ValidationRequest
from app.application.worldData.jsonValidation.validators.templates.buildingTemplate import (
    collect_building_template_issues,
)


def _run(coro):
    return asyncio.run(coro)


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"


def _load_template() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


def _town_hall() -> dict:
    tpl = deepcopy(DEFAULT_BUILDING_TEMPLATES[0])
    tpl["version"] = "1.0"
    return tpl


class TestJsonValidationJv4(unittest.TestCase):

    def test_world_template_still_ok(self):
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=_load_template(),
        )))
        self.assertTrue(result.ok, [f"{i.path}: {i.message}" for i in result.issues])

    def test_building_template_standalone_ok(self):
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUILDING_TEMPLATE,
            payload=_town_hall(),
        )))
        self.assertTrue(result.ok, result.issues)

    def test_building_template_missing_version_fails(self):
        tpl = deepcopy(DEFAULT_BUILDING_TEMPLATES[0])
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUILDING_TEMPLATE,
            payload=tpl,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.path.endswith("version") for i in result.issues))

    def test_building_template_duplicate_room_id_fails(self):
        tpl = _town_hall()
        tpl["levels"][0]["rooms"].append(deepcopy(tpl["levels"][0]["rooms"][0]))
        issues = collect_building_template_issues(tpl)
        self.assertTrue(any(i.code == "DUP_ROOM_ID" for i in issues))

    def test_district_template_standalone_ok(self):
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.DISTRICT_TEMPLATE,
            payload=deepcopy(DEFAULT_DISTRICT_TEMPLATES[0]),
        )))
        self.assertTrue(result.ok, result.issues)

    def test_barrier_template_standalone_ok(self):
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BARRIER_TEMPLATE,
            payload=deepcopy(DEFAULT_BARRIER_TEMPLATES[0]),
        )))
        self.assertTrue(result.ok, result.issues)

    def test_bundle_with_embedded_building_registry_ok(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["world"]["building_template_registry"] = [_town_hall()]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertTrue(result.ok, [f"{i.path}: {i.message}" for i in result.issues])

    def test_bundle_district_registry_unknown_building_template_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        district = deepcopy(DEFAULT_DISTRICT_TEMPLATES[0])
        district["required_structures"] = [
            {"building_template": "missing_tpl", "count": 1, "position": "center"},
        ]
        bad["world"]["district_template_registry"] = [district]
        bad["world"]["building_template_registry"] = [_town_hall()]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any("building_template" in i.path for i in result.issues))

    def test_location_building_template_uid_ref(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["world"]["building_template_registry"] = [_town_hall()]
        bad["locations"] = [{
            "location_uid": "b1",
            "display_name": "Hall",
            "system_location_type": "building",
            "system_template_uid": "unknown_uid",
            "created_at": "2026-01-01T00:00:00Z",
        }]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.path.endswith("system_template_uid") for i in result.issues))


if __name__ == "__main__":
    unittest.main()
