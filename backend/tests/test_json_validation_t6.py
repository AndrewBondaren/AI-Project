"""T6 seed import validation — docs/tz_json_validation.md."""

import asyncio
import json
import unittest
from pathlib import Path

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.types import ValidationKind, ValidationRequest
from app.application.worldData.jsonValidation.validators.seedTable import collect_seed_bundle_issues


def _run(coro):
    return asyncio.run(coro)


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "seed.json"


def _load_seed() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


class TestSeedTableValidator(unittest.TestCase):

    def test_fixture_seed_ok(self):
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.SEED,
            payload=_load_seed(),
        )))
        self.assertTrue(result.ok, result.issues)

    def test_unknown_table_fails(self):
        issues = collect_seed_bundle_issues({"not_a_table": []})
        self.assertTrue(any(i.code == "UNKNOWN_TABLE" for i in issues))

    def test_missing_pk_fails(self):
        issues = collect_seed_bundle_issues({
            "age_type": [{"display_age_type": "Adult"}],
        })
        self.assertTrue(any("system_age_type" in i.path for i in issues))

    def test_duplicate_pk_fails(self):
        issues = collect_seed_bundle_issues({
            "age_type": [
                {"system_age_type": "adult", "display_age_type": "A"},
                {"system_age_type": "adult", "display_age_type": "B"},
            ],
        })
        self.assertTrue(any(i.code == "DUP_UID" for i in issues))

    def test_social_status_weight_type(self):
        issues = collect_seed_bundle_issues({
            "social_status": [{
                "system_social_status": "x",
                "display_social_status": "X",
                "social_status_weight": "heavy",
            }],
        })
        self.assertTrue(any("social_status_weight" in i.path for i in issues))

    def test_empty_bundle_ok(self):
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.SEED,
            payload={},
        )))
        self.assertTrue(result.ok, result.issues)


if __name__ == "__main__":
    unittest.main()
