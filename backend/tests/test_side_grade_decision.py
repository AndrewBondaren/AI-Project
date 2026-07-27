"""Relief grade decision explain + facing (tz_terrain_relief R8)."""

import unittest

from app.application.worldData.generators.terrain.mountains.formGeometry import (
    construct_mountain_form,
)
from app.application.worldData.generators.terrain.mountains.sideGradeDecision import (
    explain_side_grade_at_xy,
    format_sides_summary,
    uphill_facing_toward,
)
from app.dataModel.terrainMasks.mountain.enums import MountainSideKind
from app.dataModel.terrainMasks.mountain.specs import (
    MountainFormBySides,
    MountainSideSpec,
    default_sides_for_count,
)


class TestSideGradeDecision(unittest.TestCase):
    def test_uphill_facing_toward_origin(self) -> None:
        self.assertEqual(uphill_facing_toward(10.0, 0.0, 0.0, 0.0), "west")
        self.assertEqual(uphill_facing_toward(-10.0, 0.0, 0.0, 0.0), "east")
        self.assertEqual(uphill_facing_toward(0.0, 10.0, 0.0, 0.0), "south")
        self.assertEqual(uphill_facing_toward(0.0, -10.0, 0.0, 0.0), "north")

    def test_slope_decision_has_facing_and_reason(self) -> None:
        geom = construct_mountain_form(
            MountainFormBySides(side_count=4),
            (0, 0),
            100,
        )
        sides = default_sides_for_count(4, kind=MountainSideKind.SLOPE)
        # Point east of origin on slope band
        d = explain_side_grade_at_xy(geom, sides, 50.0, 0.0, light_m=1.0)
        self.assertEqual(d.kind, MountainSideKind.SLOPE)
        self.assertEqual(d.facing, "west")  # uphill to origin
        self.assertIn("SLOPE", d.reason)
        self.assertIn("smoothstep", d.reason)

    def test_sheer_decision_facing_none(self) -> None:
        geom = construct_mountain_form(
            MountainFormBySides(side_count=4),
            (0, 0),
            100,
        )
        sides = [
            MountainSideSpec(kind=MountainSideKind.SHEER, sheer_band_light=1)
            for _ in range(4)
        ]
        # Near outer rim → SHEER step 0
        d = explain_side_grade_at_xy(geom, sides, 99.5, 0.0, light_m=1.0)
        self.assertEqual(d.kind, MountainSideKind.SHEER)
        self.assertIsNone(d.facing)
        self.assertIn("SHEER", d.reason)
        self.assertIn("отвес", d.reason)

    def test_format_sides_summary(self) -> None:
        sides = [
            MountainSideSpec(kind=MountainSideKind.SLOPE),
            MountainSideSpec(kind=MountainSideKind.SHEER, sheer_band_light=2),
        ]
        text = format_sides_summary(sides)
        self.assertIn("0=SLOPE", text)
        self.assertIn("1=SHEER(band_light=2)", text)


if __name__ == "__main__":
    unittest.main()
