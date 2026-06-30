"""T3–T5 CRUD patch validation — docs/tz_json_validation.md."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.jsonValidation.crudPatch import (
    merge_shallow_patch,
    validate_entity_row,
    validate_world_create,
    validate_world_update,
)
from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.types import SectionKey, ValidationKind, ValidationRequest


def _run(coro):
    return asyncio.run(coro)


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"


def _load_template() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


class TestCrudPatchMerge(unittest.TestCase):

    def test_merge_shallow_patch_skips_immutable(self):
        base = {"world_uid": "w1", "name": "Old", "hydrology": {"enabled": True}}
        patch = {"world_uid": "w2", "name": "New"}
        merged = merge_shallow_patch(base, patch)
        self.assertEqual(merged["world_uid"], "w1")
        self.assertEqual(merged["name"], "New")


class TestCrudPatchWorld(unittest.TestCase):

    def test_world_create_invalid_map_cell_size(self):
        bundle = _load_template()
        world = deepcopy(bundle["world"])
        world["map_cell_size_m"] = 500
        result = _run(validate_world_create(JsonValidationFacade(), world))
        self.assertFalse(result.ok)
        self.assertTrue(any("map_cell_size_m" in i.path for i in result.issues))

    def test_world_update_merged_ok(self):
        bundle = _load_template()
        existing = deepcopy(bundle["world"])
        result = _run(validate_world_update(
            JsonValidationFacade(),
            existing=existing,
            patch={"name": "Renamed world"},
            world_uid=existing["world_uid"],
        ))
        self.assertTrue(result.ok, result.issues)

    def test_crud_patch_kind_runs_world_validators(self):
        bundle = _load_template()
        world = deepcopy(bundle["world"])
        world["map_cell_size_m"] = 500
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.CRUD_PATCH,
            payload={"world": world},
            section=SectionKey.WORLD,
            world_uid=world["world_uid"],
        )))
        self.assertFalse(result.ok)


class TestCrudPatchEntity(unittest.TestCase):

    def test_location_row_invalid_type(self):
        bundle = _load_template()
        world = bundle["world"]
        row = {
            "location_uid": "loc-crud-bad",
            "world_uid": world["world_uid"],
            "display_name": "Bad",
            "system_location_type": "not_a_type",
            "created_at": "2026-01-01T00:00:00Z",
        }
        result = _run(validate_entity_row(
            JsonValidationFacade(),
            world=world,
            section=SectionKey.LOCATIONS,
            row=row,
            world_uid=world["world_uid"],
        ))
        self.assertFalse(result.ok)
        self.assertTrue(any("system_location_type" in i.path for i in result.issues))

    def test_race_row_missing_display_race(self):
        bundle = _load_template()
        world = bundle["world"]
        row = {
            "race_uid": "race-crud-bad",
            "world_uid": world["world_uid"],
            "created_at": "2026-01-01T00:00:00Z",
        }
        result = _run(validate_entity_row(
            JsonValidationFacade(),
            world=world,
            section=SectionKey.RACES,
            row=row,
            world_uid=world["world_uid"],
        ))
        self.assertFalse(result.ok)
        self.assertTrue(any("display_race" in i.path for i in result.issues))

    def test_location_row_from_template_ok(self):
        bundle = _load_template()
        world = bundle["world"]
        row = deepcopy(bundle["locations"][0])
        result = _run(validate_entity_row(
            JsonValidationFacade(),
            world=world,
            section=SectionKey.LOCATIONS,
            row=row,
            world_uid=world["world_uid"],
        ))
        self.assertTrue(result.ok, result.issues)


if __name__ == "__main__":
    unittest.main()
