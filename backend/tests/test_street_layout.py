"""DistrictTemplateEntry.street_layout — StreetLayout + DefaultOnWire."""

from __future__ import annotations

import unittest

from app.application.jsonValidation.resolve import resolve_model
from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.roads.enums.streetLayout import StreetLayout
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)


def _wire(**extra: object) -> dict[str, object]:
    return {
        "system_name": "civic_center",
        "display_name": "Центральный квартал",
        "district_type": "civic",
        **extra,
    }


class TestStreetLayoutWire(unittest.TestCase):
    def test_field_is_street_layout_default_grid(self) -> None:
        inner = unwrap_wire_type(
            DistrictTemplateEntry.model_fields["street_layout"].annotation,
        )
        self.assertIs(inner, StreetLayout)
        self.assertIs(
            DistrictTemplateEntry.model_fields["street_layout"].default,
            StreetLayout.GRID,
        )
        omitted = DistrictTemplateEntry(
            system_name="civic_center",
            display_name="x",
            district_type="civic",
        )
        self.assertIs(omitted.street_layout, StreetLayout.GRID)

    def test_wire_string_coerces(self) -> None:
        entry = DistrictTemplateEntry(
            system_name="civic_center",
            display_name="x",
            district_type="civic",
            street_layout="organic",
        )
        self.assertIs(entry.street_layout, StreetLayout.ORGANIC)

    def test_canonical_templates_are_grid(self) -> None:
        registry = WorldDistrictTemplateRegistry.canonical_defaults()
        self.assertTrue(registry.root)
        for entry in registry.root:
            self.assertIs(entry.street_layout, StreetLayout.GRID)

    def test_resolve_known_passthrough(self) -> None:
        entry = resolve_model(DistrictTemplateEntry, _wire(street_layout="grid"))
        self.assertIs(entry.street_layout, StreetLayout.GRID)

    def test_resolve_unknown_defaults_grid_and_warns(self) -> None:
        log = "app.application.jsonValidation.resolve"
        with self.assertLogs(log, level="WARNING") as captured:
            entry = resolve_model(
                DistrictTemplateEntry,
                _wire(street_layout="spiral"),
            )
        self.assertIs(entry.street_layout, StreetLayout.GRID)
        text = "\n".join(captured.output)
        self.assertIn("street_layout", text)
        self.assertIn("invalid", text)
        self.assertIn("using field default", text)

    def test_for_generator_consumes_enum(self) -> None:
        self.assertIs(
            StreetLayout.for_generator(StreetLayout.ORGANIC),
            StreetLayout.ORGANIC,
        )
        self.assertIs(StreetLayout.for_generator(None), StreetLayout.GRID)
        self.assertIs(StreetLayout.for_generator("grid"), StreetLayout.GRID)
        with self.assertRaises(ValueError):
            StreetLayout.for_generator("spiral")


if __name__ == "__main__":
    unittest.main()
