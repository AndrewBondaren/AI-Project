"""BundleNamedLocation — master wire ``description`` → ``system_description``."""

from __future__ import annotations

import unittest

from app.dataModel.locations.namedLocation import BundleNamedLocation


class BundleNamedLocationWireTests(unittest.TestCase):
    def test_description_maps_to_system_description(self) -> None:
        wire = BundleNamedLocation.model_validate({
            "location_uid": "loc-test",
            "display_name": "Test Peak",
            "system_location_type": "geographic",
            "description": "Declared peak anchor.",
        })
        fields = wire.to_db_fields()
        self.assertEqual(fields["system_description"], "Declared peak anchor.")
        self.assertNotIn("description", fields)

    def test_explicit_system_description_wins(self) -> None:
        wire = BundleNamedLocation.model_validate({
            "location_uid": "loc-test",
            "display_name": "Test Peak",
            "system_location_type": "geographic",
            "description": "shorthand",
            "system_description": "explicit",
        })
        self.assertEqual(wire.to_db_fields()["system_description"], "explicit")

    def test_display_description_preserved(self) -> None:
        wire = BundleNamedLocation.model_validate({
            "location_uid": "loc-test",
            "display_name": "Test",
            "system_location_type": "settlement",
            "display_description": "Narrative for LLM.",
        })
        self.assertEqual(wire.to_db_fields()["display_description"], "Narrative for LLM.")


if __name__ == "__main__":
    unittest.main()
