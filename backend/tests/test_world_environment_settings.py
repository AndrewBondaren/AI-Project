"""SP-A1: World atmosphere is explicit and cannot be inferred from empty space."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from pydantic import ValidationError

from app.application.jsonValidation.index.validate import validate_ref_w
from app.application.jsonValidation.worldRow import world_environment
from app.application.jsonValidation.worldSlices import slice_column_key
from app.dataModel.worldEnvironment.worldEnvironmentSettings import (
    WorldAtmosphereSettings,
    WorldEnvironmentSettings,
)


def _mixture(*entries: tuple[str, float]) -> dict:
    return {
        "mode": "mixture",
        "composition": [
            {"system_material": key, "fraction": share}
            for key, share in entries
        ],
    }


class WorldEnvironmentSettingsTest(unittest.TestCase):
    def test_missing_atmosphere_is_unresolved_not_air_or_vacuum(self) -> None:
        self.assertIsNone(WorldEnvironmentSettings.model_validate({}).atmosphere)
        self.assertIsNone(world_environment(SimpleNamespace(world_uid="w")).atmosphere)
        self.assertEqual(slice_column_key(WorldEnvironmentSettings), "world_environment")

    def test_explicit_vacuum_and_gas_mixture(self) -> None:
        vacuum = WorldEnvironmentSettings.model_validate({
            "atmosphere": {"mode": "vacuum"},
        })
        self.assertEqual(vacuum.atmosphere.mode, "vacuum")
        self.assertEqual(vacuum.atmosphere.composition, [])
        gases = WorldEnvironmentSettings.model_validate({
            "atmosphere": _mixture(("nitrogen", 0.8), ("oxygen", 0.2)),
        })
        self.assertEqual(gases.atmosphere.mode, "mixture")
        self.assertEqual(gases.model_dump(mode="json")["atmosphere"]["composition"][1]["system_material"],
                         "oxygen")

    def test_invalid_composition_is_rejected(self) -> None:
        invalid = [
            {"mode": "vacuum", "composition": [{"system_material": "air", "fraction": 1.0}]},
            _mixture(),
            _mixture(("air", 0.5)),
            _mixture(("air", 0.5), ("air", 0.5)),
            _mixture(("air", 0.0), ("oxygen", 1.0)),
        ]
        for entry in invalid:
            with self.subTest(entry=entry), self.assertRaises(ValidationError):
                WorldAtmosphereSettings.model_validate(entry)

    def test_gas_ref_cannot_point_to_solid_material(self) -> None:
        world_wire = {
            "material_registry": [
                {"system_material": "air", "material_category": "gas"},
                {"system_material": "stone", "material_category": "solid"},
            ],
            "world_environment": {"atmosphere": _mixture(("stone", 1.0))},
        }
        issues = validate_ref_w(world_wire, partial=False)
        self.assertTrue(any(
            issue.code == "REF_W_UNKNOWN"
            and issue.path == ("world_environment", "atmosphere", "composition", 0, "system_material")
            for issue in issues
        ), issues)
        world_wire["world_environment"]["atmosphere"] = _mixture(("air", 1.0))
        self.assertFalse(any(issue.code == "REF_W_UNKNOWN" for issue in
                             validate_ref_w(world_wire, partial=False)))


if __name__ == "__main__":
    unittest.main()
