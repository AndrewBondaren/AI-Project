"""PerimeterBarrier.sides — cardinal Facing list + skip unknown."""

from __future__ import annotations

import unittest

from app.application.jsonValidation.resolve import resolve_model
from app.dataModel.settlement.area.perimeterBarrier import (
    PerimeterBarrier,
    resolved_host_sides,
)
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing


class TestPerimeterBarrierSides(unittest.TestCase):
    def test_omit_and_empty_mean_all_cardinals(self) -> None:
        omitted = PerimeterBarrier()
        self.assertIsNone(omitted.sides)
        sides, skipped = resolved_host_sides(omitted)
        self.assertEqual(sides, CARDINAL_FACINGS)
        self.assertEqual(skipped, [])

        empty = PerimeterBarrier(sides=[])
        self.assertEqual(empty.sides, [])
        sides, skipped = resolved_host_sides(empty)
        self.assertEqual(sides, CARDINAL_FACINGS)
        self.assertEqual(skipped, [])

    def test_wire_keeps_cardinals(self) -> None:
        barrier = PerimeterBarrier(sides=["north", "east"])
        self.assertEqual(barrier.sides, [Facing.NORTH, Facing.EAST])
        sides, skipped = resolved_host_sides(barrier)
        self.assertEqual(sides, frozenset({Facing.NORTH, Facing.EAST}))
        self.assertEqual(skipped, [])

    def test_compact_letter_coerces(self) -> None:
        barrier = PerimeterBarrier(sides=["N", "W"])
        self.assertEqual(barrier.sides, [Facing.NORTH, Facing.WEST])

    def test_skip_intercardinal_and_unknown_keeps_rest(self) -> None:
        log = "app.dataModel.settlement.area.perimeterBarrier"
        with self.assertLogs(log, level="WARNING") as captured:
            barrier = PerimeterBarrier(
                sides=["north", "north_east", "nope", "south"],
            )
        self.assertEqual(barrier.sides, [Facing.NORTH, Facing.SOUTH])
        text = "\n".join(captured.output)
        self.assertIn("skip", text)
        self.assertIn("north_east", text)
        self.assertIn("nope", text)
        sides, skipped = resolved_host_sides(barrier)
        self.assertEqual(sides, frozenset({Facing.NORTH, Facing.SOUTH}))
        self.assertEqual(skipped, [])

    def test_skip_all_means_all_cardinals(self) -> None:
        log = "app.dataModel.settlement.area.perimeterBarrier"
        with self.assertLogs(log, level="WARNING") as captured:
            barrier = PerimeterBarrier(sides=["north_east", "nope"])
        self.assertEqual(barrier.sides, [])
        text = "\n".join(captured.output)
        self.assertIn("skip", text)
        sides, skipped = resolved_host_sides(barrier)
        self.assertEqual(sides, CARDINAL_FACINGS)

    def test_dedupe_preserves_order(self) -> None:
        barrier = PerimeterBarrier(sides=["east", "north", "east"])
        self.assertEqual(barrier.sides, [Facing.EAST, Facing.NORTH])

    def test_resolve_non_list_defaults_none_and_warns(self) -> None:
        log = "app.application.jsonValidation.resolve"
        with self.assertLogs(log, level="WARNING") as captured:
            barrier = resolve_model(
                PerimeterBarrier,
                {"template": "stone_fence", "sides": "north"},
            )
        self.assertIsNone(barrier.sides)
        text = "\n".join(captured.output)
        self.assertIn("sides", text)
        self.assertIn("invalid", text)
        self.assertIn("using field default", text)

    def test_resolve_mixed_list_keeps_cardinals(self) -> None:
        barrier = resolve_model(
            PerimeterBarrier,
            {"sides": ["west", "nope", "south"]},
        )
        self.assertEqual(barrier.sides, [Facing.WEST, Facing.SOUTH])


if __name__ == "__main__":
    unittest.main()
