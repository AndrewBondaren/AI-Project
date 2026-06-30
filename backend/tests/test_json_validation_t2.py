"""T2 section import — synthetic bundle validation for all wired sections."""

import asyncio
import json
import unittest
from pathlib import Path

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.sectionImport import (
    SECTIONS_REQUIRING_SEED,
    validate_section_import,
)
from app.application.worldData.jsonValidation.syntheticBundle import build_synthetic_bundle
from app.application.worldData.jsonValidation.types import SectionKey, ValidationKind, ValidationRequest


def _run(coro):
    return asyncio.run(coro)


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"

_MIN_SEED = {
    "age_type": [
        {"system_age_type": "child", "display_age_type": "Child"},
        {"system_age_type": "adult", "display_age_type": "Adult"},
    ],
}


def _load_template() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


class TestSectionImportT2(unittest.TestCase):

    def test_sections_requiring_seed_includes_races(self):
        self.assertIn(SectionKey.RACES, SECTIONS_REQUIRING_SEED)

    def test_synthetic_section_races_ok(self):
        bundle = _load_template()
        world = bundle["world"]
        payload = list(bundle["races"])
        synthetic = build_synthetic_bundle(world, SectionKey.RACES, payload)
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.SECTION,
            payload=synthetic,
            section=SectionKey.RACES,
            world_uid=world["world_uid"],
            seed_snapshot=_MIN_SEED,
        )))
        self.assertTrue(result.ok, result.issues)

    def test_synthetic_section_races_bad_row_fails(self):
        bundle = _load_template()
        world = bundle["world"]
        payload = [{"race_uid": "r1", "created_at": "2026-01-01T00:00:00Z"}]
        synthetic = build_synthetic_bundle(world, SectionKey.RACES, payload)
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.SECTION,
            payload=synthetic,
            section=SectionKey.RACES,
            world_uid=world["world_uid"],
        )))
        self.assertFalse(result.ok)
        self.assertTrue(any("display_race" in i.path for i in result.issues))

    def test_synthetic_section_perks_empty_ok(self):
        bundle = _load_template()
        world = bundle["world"]
        synthetic = build_synthetic_bundle(world, SectionKey.PERKS, [])
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.SECTION,
            payload=synthetic,
            section=SectionKey.PERKS,
            world_uid=world["world_uid"],
        )))
        self.assertTrue(result.ok, result.issues)

    def test_synthetic_section_map_cells_empty_ok(self):
        bundle = _load_template()
        world = bundle["world"]
        synthetic = build_synthetic_bundle(world, SectionKey.MAP_CELLS, [])
        result = _run(JsonValidationFacade().validate(ValidationRequest(
            kind=ValidationKind.SECTION,
            payload=synthetic,
            section=SectionKey.MAP_CELLS,
            world_uid=world["world_uid"],
        )))
        self.assertTrue(result.ok, result.issues)

    def test_validate_section_import_helper(self):
        bundle = _load_template()
        world = bundle["world"]
        result = _run(validate_section_import(
            JsonValidationFacade(),
            world=world,
            section=SectionKey.LOCATIONS,
            payload=[bundle["locations"][0]],
            world_uid=world["world_uid"],
        ))
        self.assertTrue(result.ok, result.issues)


if __name__ == "__main__":
    unittest.main()
