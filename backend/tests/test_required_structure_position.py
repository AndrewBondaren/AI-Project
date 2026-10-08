"""RequiredStructure.position — RequiredStructurePosition + DefaultOnWire."""

from __future__ import annotations

from app.application.jsonValidation.resolve import UnresolvedModelError, ResolveContext, resolve_result
from pydantic import ValidationError
import unittest

from app.application.jsonValidation.resolve import resolve_model
from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.locations.settlement.district.requiredStructure import (
    POSITION_ANY,
    POSITION_CENTER,
    RequiredStructure,
)
from app.dataModel.locations.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)
from app.dataModel.locations.settlement.enums.requiredStructurePosition import (
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
        omitted = RequiredStructure(plot_template="town_hall")
        self.assertIs(omitted.position, RequiredStructurePosition.ANY)

    def test_wire_string_coerces(self) -> None:
        entry = RequiredStructure(
            plot_template="town_hall",
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

    def test_resolve_unknown_rejects(self):
        with self.assertLogs("app.application.jsonValidation.resolve", "WARNING") as logs:
            result = resolve_result(RequiredStructure, _wire(position="edge"))
        self.assertFalse(result.resolved)
        self.assertEqual(result.issues[0].path, ("position",))
        self.assertIn("WarningError", logs.output[0])

    def test_resolve_blank_rejects(self):
        with self.assertLogs("app.application.jsonValidation.resolve", "WARNING") as logs:
            result = resolve_result(RequiredStructure, _wire(position=""))
        self.assertFalse(result.resolved)
        self.assertEqual(result.issues[0].path, ("position",))
        self.assertIn("WarningError", logs.output[0])

    def test_direct_unknown_rejects(self):
        for value in ("edge", ""):
            with self.assertRaises(ValidationError):
                RequiredStructure(plot_template="market", position=value)

    def test_aliases_are_enum_members(self) -> None:
        self.assertIs(POSITION_ANY, RequiredStructurePosition.ANY)
        self.assertIs(POSITION_CENTER, RequiredStructurePosition.CENTER)
        self.assertEqual(POSITION_CENTER, "center")

    def test_plot_template_leftover_alias(self) -> None:
        leftover = RequiredStructure.model_validate({"building_template": "town_hall"})
        self.assertEqual(leftover.plot_template, "town_hall")
        dumped = leftover.model_dump(mode="json")
        self.assertEqual(dumped["plot_template"], "town_hall")
        self.assertNotIn("building_template", dumped)
        canon = RequiredStructure(plot_template="inn_small")
        self.assertEqual(canon.plot_template, "inn_small")


if __name__ == "__main__":
    unittest.main()
