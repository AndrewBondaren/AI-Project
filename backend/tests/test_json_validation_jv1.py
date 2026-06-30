"""Unit tests for jsonValidation Phase 1 — JV-1 envelope, world row, N1-S."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.types import ValidationKind, ValidationRequest


def _run(coro):
    return asyncio.run(coro)


def _minimal_world(**overrides) -> dict:
    base = {
        "world_uid": "w1",
        "name": "Test",
        "created_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


class TestJsonValidationJv1(unittest.TestCase):

    def test_envelope_missing_world(self):
        facade = JsonValidationFacade()
        result = _run(facade.validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload={"races": []},
        )))
        self.assertFalse(result.ok)
        codes = {i.code for i in result.issues}
        self.assertIn("MISSING_KEY", codes)

    def test_envelope_missing_world_uid(self):
        facade = JsonValidationFacade()
        result = _run(facade.validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload={"world": {"name": "No uid"}},
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.path == "world.world_uid" for i in result.issues))

    def test_world_row_map_cell_size(self):
        facade = JsonValidationFacade()
        result = _run(facade.validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload={"world": _minimal_world(map_cell_size_m=500)},
        )))
        self.assertFalse(result.ok)
        self.assertTrue(
            any(i.schema_id == "SCH-WORLD-ROW" and "map_cell_size_m" in i.path
                for i in result.issues),
        )

    def test_n1s_stat_schema_map_to_array(self):
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"
        with fixture_path.open(encoding="utf-8") as f:
            bundle = json.load(f)
        world = deepcopy(bundle["world"])
        stat_map = world["stat_schema"]
        self.assertIsInstance(stat_map, dict)

        facade = JsonValidationFacade()
        result = _run(facade.validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload={"world": world},
        )))
        self.assertTrue(result.ok, result.issues)
        normalized = result.normalized
        assert isinstance(normalized, dict)
        rows = normalized["world"]["stat_schema"]
        self.assertIsInstance(rows, list)
        names = {row["system_name"] for row in rows}
        self.assertEqual(names, set(stat_map.keys()))
        for row in rows:
            self.assertIn("system_name", row)
            self.assertIn(row["system_name"], stat_map)

    def test_payload_not_mutated(self):
        payload = {"world": _minimal_world(stat_schema={"hp": {"display_name": "HP"}})}
        original = deepcopy(payload)
        facade = JsonValidationFacade()
        _run(facade.validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=payload,
        )))
        self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
