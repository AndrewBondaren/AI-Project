"""RequiredStructure.position — RequiredStructurePosition + DefaultOnWire."""

from __future__ import annotations

import unittest

from app.application.jsonValidation.resolve import resolve_model
from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.settlement.district.requiredStructure import (
    POSITION_ANY,
    POSITION_CENTER,
    RequiredStructure,
)
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)
from app.dataModel.settlement.enums.requiredStructurePosition import (
    RequiredStructurePosition,
)


def _wire(**extra: object) -> dict[str, object]:
    return {"building_template": "town_hall", **extra}


class TestRequiredStructurePositionWire(unittest.TestCase):
    def test_field_defaults_to_any(self) -> None:
        inner = unwrap_wire_type(
            RequiredStructure.model_fields["position"].annotation,
        )
        self.assertIs(inner, RequiredStructurePosition)
        self.assertIs(
            RequiredStructure.model_fields["position"].default,
            POSITION_ANY,
        )
        omitted = RequiredStructure(building_template="town_hall")
        self.assertIs(omitted.position, RequiredStructurePosition.ANY)

    def test_wire_string_coerces(self) -> None:
        entry = RequiredStructure(
            building_template="town_hall",
            position="center",
        )
        self.assertIs(entry.position, RequiredStructurePosition.CENTER)
        self.assertEqual(entry.position, POSITION_CENTER)

    def test_canonical_civic_town_hall_is_center(self) -> None:
        civic = WorldDistrictTemplateRegistry.canonical_defaults().entry_for(
            "civic_center",
        )
        assert civic is not None
        assert civic.required_structures is not None
        self.assertIs(
            civic.required_structures[0].position,
            RequiredStructurePosition.CENTER,
        )

    def test_resolve_known_passthrough(self) -> None:
        entry = resolve_model(RequiredStructure, _wire(position="any"))
        self.assertIs(entry.position, RequiredStructurePosition.ANY)

    def test_resolve_unknown_defaults_any_and_warns(self) -> None:
        log = "app.application.jsonValidation.resolve"
        with self.assertLogs(log, level="WARNING") as captured:
            entry = resolve_model(
                RequiredStructure,
                _wire(position="edge"),
            )
        self.assertIs(entry.position, RequiredStructurePosition.ANY)
        text = "\n".join(captured.output)
        self.assertIn("position", text)
        self.assertIn("invalid", text)
        self.assertIn("using field default", text)

    def test_resolve_blank_defaults_any_and_warns(self) -> None:
        log = "app.application.jsonValidation.resolve"
        with self.assertLogs(log, level="WARNING") as captured:
            entry = resolve_model(RequiredStructure, _wire(position=""))
        self.assertIs(entry.position, RequiredStructurePosition.ANY)
        text = "\n".join(captured.output)
        self.assertIn("position", text)
        self.assertIn("invalid", text)

    def test_direct_unknown_coerces_to_any(self) -> None:
        entry = RequiredStructure(building_template="market", position="edge")
        self.assertIs(entry.position, RequiredStructurePosition.ANY)
        blank = RequiredStructure(building_template="town_hall", position="")
        self.assertIs(blank.position, RequiredStructurePosition.ANY)

    def test_aliases_are_enum_members(self) -> None:
        self.assertIs(POSITION_ANY, RequiredStructurePosition.ANY)
        self.assertIs(POSITION_CENTER, RequiredStructurePosition.CENTER)
        self.assertEqual(POSITION_CENTER, "center")


if __name__ == "__main__":
    unittest.main()
