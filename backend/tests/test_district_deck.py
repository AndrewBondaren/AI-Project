"""DistrictTemplateEntry.deck — ярус района, omit → 0."""

from __future__ import annotations

import unittest

from app.application.jsonValidation.resolve import resolve_model
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


class TestDistrictDeck(unittest.TestCase):
    def test_omit_is_surface(self) -> None:
        entry = DistrictTemplateEntry(
            system_name="civic_center",
            display_name="x",
            district_type="civic",
        )
        self.assertEqual(entry.deck, 0)

    def test_explicit_deck(self) -> None:
        entry = DistrictTemplateEntry(
            system_name="civic_center",
            display_name="x",
            district_type="civic",
            deck=-1,
        )
        self.assertEqual(entry.deck, -1)

    def test_canonical_templates_are_surface(self) -> None:
        registry = WorldDistrictTemplateRegistry.canonical_defaults()
        self.assertTrue(registry.root)
        for entry in registry.root:
            self.assertEqual(entry.deck, 0)

    def test_resolve_omit(self) -> None:
        entry = resolve_model(DistrictTemplateEntry, _wire())
        self.assertEqual(entry.deck, 0)

    def test_resolve_int(self) -> None:
        entry = resolve_model(DistrictTemplateEntry, _wire(deck=2))
        self.assertEqual(entry.deck, 2)

    def test_resolve_invalid_defaults_zero_and_warns(self) -> None:
        log = "app.application.jsonValidation.resolve"
        with self.assertLogs(log, level="WARNING") as captured:
            entry = resolve_model(DistrictTemplateEntry, _wire(deck="surface"))
        self.assertEqual(entry.deck, 0)
        text = "\n".join(captured.output)
        self.assertIn("deck", text)
        self.assertIn("using field default", text)


if __name__ == "__main__":
    unittest.main()
