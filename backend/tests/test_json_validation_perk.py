"""SCH-PERK-ROW validation — docs/tz_json_validation.md phase 9."""

import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.jsonValidation.crudPatch import validate_entity_row
from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.index.worldRegistryIndex import build_world_registry_index
from app.application.worldData.jsonValidation.types import SectionKey, ValidationKind, ValidationRequest
from app.application.worldData.jsonValidation.validators.perkRow import collect_perk_row_issues


def _run(coro):
    return asyncio.run(coro)


WORLD_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_test.json"
TEMPLATE = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"


def _load_world_test() -> dict:
    with WORLD_FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


def _load_template() -> dict:
    with TEMPLATE.open(encoding="utf-8") as f:
        return json.load(f)


def _valid_perk() -> dict:
    return {
        "perk_uid": "perk-smoke",
        "system_name": "iron_will",
        "display_name": "Iron Will",
        "system_description": "Resistance to fear",
        "display_description": "Устойчивость к страху",
    }


class TestPerkRowValidator(unittest.TestCase):

    def test_world_test_perks_ok(self):
        bundle = _load_world_test()
        index = build_world_registry_index(bundle["world"])
        issues = collect_perk_row_issues(bundle["perks"], index)
        self.assertEqual(issues, [], issues)

    def test_missing_display_name_fails(self):
        issues = collect_perk_row_issues([{
            "perk_uid": "p1",
            "system_name": "x",
        }])
        self.assertTrue(any("display_name" in i.path for i in issues))

    def test_invalid_rank_value_shape(self):
        issues = collect_perk_row_issues([{
            "perk_uid": "p1",
            "system_name": "x",
            "display_name": "X",
            "system_rank_value": [{"rank": "basic", "value": [5, 1]}],
        }])
        self.assertTrue(any(i.code == "OUT_OF_RANGE" for i in issues))

    def test_duplicate_system_name_fails(self):
        row = {
            "perk_uid": "p1",
            "system_name": "dup",
            "display_name": "A",
        }
        issues = collect_perk_row_issues([row, deepcopy(row) | {"perk_uid": "p2"}])
        self.assertTrue(any(i.code == "DUP_KEY" for i in issues))

    def test_synthetic_section_perks(self):
        bundle = _load_template()
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.SECTION,
            payload={"world": bundle["world"], "perks": [_valid_perk()]},
            section=SectionKey.PERKS,
            world_uid=bundle["world"]["world_uid"],
        )))
        self.assertTrue(result.ok, result.issues)

    def test_entity_crud_valid_perk(self):
        bundle = _load_template()
        result = _run(validate_entity_row(
            JsonValidationFacade(),
            world=bundle["world"],
            section=SectionKey.PERKS,
            row=_valid_perk(),
            world_uid=bundle["world"]["world_uid"],
        ))
        self.assertTrue(result.ok, result.issues)


if __name__ == "__main__":
    unittest.main()
