"""Unit tests for jsonValidation Phase 0 — docs/tz_json_validation.md."""

import asyncio
import unittest

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.http import format_validation_issues
from app.application.worldData.jsonValidation.registry import ValidatorRegistry
from app.application.worldData.jsonValidation.types import (
    SectionKey,
    ValidationIssue,
    ValidationKind,
    ValidationRequest,
    ValidationResult,
    active_section_keys,
)


def _run(coro):
    return asyncio.run(coro)


class _StubValidator:
    schema_id = "SCH-STUB"
    sections = frozenset({SectionKey.WORLD})

    def __init__(self, issue: ValidationIssue | None = None) -> None:
        self._issue = issue

    def validate(self, ctx) -> None:
        if self._issue is not None:
            ctx.issues.append(self._issue)


class TestJsonValidationFacade(unittest.TestCase):

    def test_bundle_ok_phase0(self):
        facade = JsonValidationFacade()
        result = _run(facade.validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload={
                "world": {
                    "world_uid": "w1",
                    "name": "Test",
                    "created_at": "2026-01-01T00:00:00Z",
                },
            },
        )))
        self.assertTrue(result.ok)
        self.assertEqual(result.issues, [])
        self.assertIsInstance(result.normalized, dict)

    def test_seed_ok_phase0(self):
        facade = JsonValidationFacade()
        result = _run(facade.validate(ValidationRequest(
            kind=ValidationKind.SEED,
            payload={"hair_type": []},
        )))
        self.assertTrue(result.ok)

    def test_character_delegates_stub_ok(self):
        facade = JsonValidationFacade()
        result = _run(facade.validate(ValidationRequest(
            kind=ValidationKind.CHARACTER,
            payload={"name": "Hero"},
        )))
        self.assertTrue(result.ok)

    def test_registry_validator_failure(self):
        issue = ValidationIssue(
            schema_id="SCH-WORLD-ROW",
            path="world.map_cell_size_m",
            code="OUT_OF_RANGE",
            message="map_cell_size_m must be >= 1000",
        )
        registry = ValidatorRegistry([_StubValidator(issue)])
        facade = JsonValidationFacade(registry=registry)
        result = _run(facade.validate(ValidationRequest(
            kind=ValidationKind.BUNDLE,
            payload={"world": {"world_uid": "w1"}},
        )))
        self.assertFalse(result.ok)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].code, "OUT_OF_RANGE")

    def test_active_section_keys(self):
        bundle = {
            "world": {"world_uid": "w1"},
            "races": [],
            "locations": [],
        }
        keys = active_section_keys(bundle)
        self.assertIn(SectionKey.WORLD, keys)
        self.assertIn(SectionKey.RACES, keys)
        self.assertIn(SectionKey.LOCATIONS, keys)
        self.assertNotIn(SectionKey.MAP_CELLS, keys)


class TestValidationHttpFormat(unittest.TestCase):

    def test_format_validation_issues(self):
        result = ValidationResult(
            ok=False,
            issues=[
                ValidationIssue(
                    schema_id="SCH-WORLD-BUNDLE-ENVELOPE",
                    path="world",
                    code="MISSING_KEY",
                    message="Bundle must contain 'world' key",
                ),
            ],
        )
        body = format_validation_issues(result)
        self.assertTrue(body["validation_failed"])
        self.assertEqual(body["error_count"], 1)
        self.assertEqual(body["issues"][0]["schema_id"], "SCH-WORLD-BUNDLE-ENVELOPE")


if __name__ == "__main__":
    unittest.main()
