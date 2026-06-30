"""Unit tests for jsonValidation Phase 3 — JV-3 hydrology + climate."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.normalize.hydrologyDefaults import TYPE_CLASSIFY_DEFAULTS
from app.application.worldData.jsonValidation.types import ValidationKind, ValidationRequest


def _run(coro):
    return asyncio.run(coro)


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"


def _load_template() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


class TestJsonValidationJv3(unittest.TestCase):

    def test_world_template_still_ok(self):
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=_load_template(),
        )))
        self.assertTrue(result.ok, [f"{i.path}: {i.message}" for i in result.issues])

    def test_type_classify_nulls_normalized(self):
        bundle = _load_template()
        world = deepcopy(bundle["world"])
        world["hydrology"]["default_rivers"]["type_classify"]["mountain_min_source_z"] = None
        world["hydrology"]["default_rivers"]["type_classify"]["foothill_gradient_threshold"] = None
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload={"world": world},
        )))
        self.assertTrue(result.ok, result.issues)
        tc = result.normalized["world"]["hydrology"]["default_rivers"]["type_classify"]
        self.assertEqual(tc["mountain_min_source_z"], TYPE_CLASSIFY_DEFAULTS["mountain_min_source_z"])
        self.assertEqual(tc["foothill_gradient_threshold"], TYPE_CLASSIFY_DEFAULTS["foothill_gradient_threshold"])

    def test_river_bands_min_gt_max_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["world"]["hydrology"]["default_rivers"]["bands"] = {"min": 10, "max": 2}
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any("bands.max" in i.path or "bands" in i.path for i in result.issues))

    def test_peak_min_gt_max_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["world"]["climate_temperature_peak_min"] = 50
        bad["world"]["climate_temperature_peak_max"] = 10
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any("climate_temperature_peak" in i.path for i in result.issues))

    def test_invalid_precipitation_liquid_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["world"]["precipitation_liquid"] = "stone"
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.path == "world.precipitation_liquid" for i in result.issues))

    def test_z_min_gt_z_max_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["world"]["z_min"] = 100
        bad["world"]["z_max"] = 50
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.path == "world.z_min" for i in result.issues))

    def test_invalid_season_key_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["world"]["season_temp_offsets"] = {"monsoon": 5}
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any("season_temp_offsets" in i.path for i in result.issues))


if __name__ == "__main__":
    unittest.main()
