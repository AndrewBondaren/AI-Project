"""Unit tests for jsonValidation Phase 5 — JV-8 race contract + seed index."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.index.seedRegistryIndex import build_seed_registry_index
from app.application.worldData.jsonValidation.types import ValidationKind, ValidationRequest
from app.application.worldData.jsonValidation.validators.raceContract import collect_race_contract_issues


def _run(coro):
    return asyncio.run(coro)


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"

_MIN_SEED = {
    "age_type": [
        {"system_age_type": "child", "display_age_type": "Child"},
        {"system_age_type": "adult", "display_age_type": "Adult"},
    ],
    "hair_type": [{"system_hair_type": "straight", "display_hair_type": "Straight"}],
}


def _load_template() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


class TestSeedRegistryIndex(unittest.TestCase):

    def test_build_from_export(self):
        index = build_seed_registry_index(_MIN_SEED)
        self.assertTrue(index.has_seed("age_type", "child"))
        self.assertTrue(index.has_seed("hair_type", "straight"))


class TestJsonValidationJv5(unittest.TestCase):

    def test_world_template_still_ok(self):
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=_load_template(),
        )))
        self.assertTrue(result.ok, [f"{i.path}: {i.message}" for i in result.issues])

    def test_missing_display_race_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["races"] = [{
            "race_uid": "r1",
            "created_at": "2026-01-01T00:00:00Z",
        }]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.path.endswith("display_race") for i in result.issues))

    def test_duplicate_race_uid_fails(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        row = deepcopy(bad["races"][0])
        bad["races"] = [row, deepcopy(row)]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any(i.code == "DUP_UID" for i in result.issues))

    def test_gender_blob_must_be_object(self):
        bundle = _load_template()
        bad = deepcopy(bundle)
        bad["races"] = [{
            "race_uid": "r1",
            "display_race": "Test",
            "created_at": "2026-01-01T00:00:00Z",
            "male": "not-an-object",
        }]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=bad,
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any("male" in i.path for i in result.issues))

    def test_lifespan_overlap_fails(self):
        race = {
            "race_uid": "r1",
            "display_race": "Test",
            "created_at": "2026-01-01T00:00:00Z",
            "male": {
                "lifespan": [
                    {"from": 0, "to": 20, "age_type": "child"},
                    {"from": 15, "to": 100, "age_type": "adult"},
                ],
            },
        }
        seed = build_seed_registry_index(_MIN_SEED)
        issues = collect_race_contract_issues([race], index=None, seed_index=seed)
        self.assertTrue(any(i.code == "LIFESPAN_OVERLAP" for i in issues))

    def test_unknown_age_type_with_seed_fails(self):
        race = {
            "race_uid": "r1",
            "display_race": "Test",
            "created_at": "2026-01-01T00:00:00Z",
            "female": {
                "lifespan": [{"from": 0, "to": 100, "age_type": "elder"}],
            },
        }
        seed = build_seed_registry_index(_MIN_SEED)
        issues = collect_race_contract_issues([race], index=None, seed_index=seed)
        self.assertTrue(any("age_type" in i.path for i in issues))

    def test_bundle_with_seed_snapshot_validates_age_type(self):
        bundle = _load_template()
        good = deepcopy(bundle)
        good["races"] = [{
            "race_uid": "race-human",
            "display_race": "Human",
            "created_at": "2026-01-01T00:00:00Z",
            "male": {
                "lifespan": [
                    {"from": 0, "to": 15, "age_type": "child"},
                    {"from": 16, "to": 120, "age_type": "adult"},
                ],
            },
        }]
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload=good,
            seed_snapshot=_MIN_SEED,
        )))
        self.assertTrue(result.ok, result.issues)


if __name__ == "__main__":
    unittest.main()
