"""BundleNamedLocation — master wire ``description`` → ``system_description``."""

from __future__ import annotations

import unittest

from app.dataModel.locations.namedLocation import BundleNamedLocation
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.settlement.settlement.settlementSkeleton import SettlementSkeleton


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

    def test_settlement_skeleton_overlay_reaches_db_fields(self) -> None:
        density = DistrictDensity.MEDIUM.wire_value
        barrier = PerimeterBarrier(template="stone_fence", probability=1.0)
        wire = BundleNamedLocation.model_validate({
            "location_uid": "loc-city",
            "display_name": "Ironhold",
            "system_location_type": "settlement",
            "settlement_density": density,
            "architectural_style": "gothic",
            "perimeter_barrier": barrier.model_dump(mode="json"),
            "frontage_type_order": ["road", "dirt_road"],
            "plot_counts": {"tavern_1": 2},
            "plot_priority": {"tavern_1": 1},
        })
        fields = wire.to_db_fields()
        self.assertEqual(fields["settlement_density"], density)
        self.assertEqual(fields["architectural_style"], "gothic")
        self.assertEqual(
            fields["settlement_density"],
            SettlementSkeleton.model_validate(
                {"settlement_density": density},
            ).settlement_density,
        )
        self.assertEqual(fields["perimeter_barrier"]["template"], barrier.template)
        self.assertEqual(fields["frontage_type_order"], ["road", "dirt_road"])
        self.assertEqual(fields["plot_counts"]["tavern_1"], 2)
        self.assertEqual(fields["plot_priority"]["tavern_1"], 1)

    def test_legacy_structure_counts_alias(self) -> None:
        wire = BundleNamedLocation.model_validate({
            "location_uid": "loc-city",
            "display_name": "Ironhold",
            "system_location_type": "settlement",
            "structure_counts": {"tavern_1": 2},
            "structure_priority": {"tavern_1": 1},
        })
        self.assertEqual(wire.plot_counts["tavern_1"], 2)
        self.assertEqual(wire.plot_priority["tavern_1"], 1)
        fields = wire.to_db_fields()
        self.assertEqual(fields["plot_counts"]["tavern_1"], 2)
        self.assertNotIn("structure_counts", fields)


if __name__ == "__main__":
    unittest.main()
