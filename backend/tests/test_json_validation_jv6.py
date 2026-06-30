"""Unit tests for jsonValidation Phase 6 — JV-6 character package."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.types import ValidationKind, ValidationRequest


def _run(coro):
    return asyncio.run(coro)


ROOT = Path(__file__).resolve().parents[2]
CHARACTER = ROOT / "fixtures" / "character_test.json"
WORLD = ROOT / "fixtures" / "world_template.json"

_MIN_SEED = {
    "age_type": [{"system_age_type": "adult", "display_age_type": "Adult"}],
    "social_status": [{"system_social_status": "commoner", "display_social_status": "Commoner"}],
}


def _load_character() -> dict:
    with CHARACTER.open(encoding="utf-8") as f:
        return json.load(f)


def _load_world() -> dict:
    with WORLD.open(encoding="utf-8") as f:
        return json.load(f)["world"]


class TestJsonValidationJv6(unittest.TestCase):

    def test_character_row_only_ok(self):
        sheet = _load_character()
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
        )))
        self.assertTrue(result.ok, result.issues)

    def test_missing_display_name_fails(self):
        sheet = _load_character()
        del sheet["display_name"]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.path == "display_name" for i in result.issues))

    def test_unknown_field_fails(self):
        sheet = _load_character()
        sheet["not_a_player_field"] = True
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.code == "UNKNOWN_FIELD" for i in result.issues))

    def test_with_world_context_stats_ok(self):
        sheet = _load_character()
        world = _load_world()
        races = [{"race_uid": "race-human", "display_race": "Human", "created_at": "2026-01-01T00:00:00Z"}]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
            world_context=world,
            races_snapshot=races,
            seed_snapshot=_MIN_SEED,
        )))
        self.assertTrue(result.ok, [f"{i.path}: {i.message}" for i in result.issues])

    def test_unknown_stat_key_fails(self):
        sheet = _load_character()
        sheet["system_stats"]["magic"] = 10
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
            world_context=_load_world(),
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any("system_stats" in i.path for i in result.issues))

    def test_unknown_race_fails(self):
        sheet = _load_character()
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
            world_context=_load_world(),
            races_snapshot=[{"race_uid": "other-race"}],
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.path == "system_race" for i in result.issues))

    def test_invalid_gender_fails(self):
        sheet = _load_character()
        sheet["system_gender"] = "robot"
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.path == "system_gender" for i in result.issues))

    def test_stat_out_of_range_fails(self):
        sheet = _load_character()
        sheet["system_stats"]["strength"] = 99
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
            world_context=_load_world(),
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.code == "OUT_OF_RANGE" for i in result.issues))

    def test_world_schema_version_mismatch_fails(self):
        sheet = _load_character()
        sheet["world_schema_version"] = "old-hash"
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
            world_context=_load_world(),
            expected_world_schema_version="current-hash",
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.code == "SCHEMA_VERSION_MISMATCH" for i in result.issues))

    def test_world_schema_version_normalized_on_import(self):
        sheet = _load_character()
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload=sheet,
            world_context=_load_world(),
            expected_world_schema_version="current-hash",
        )))
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.normalized["world_schema_version"], "current-hash")


if __name__ == "__main__":
    unittest.main()
