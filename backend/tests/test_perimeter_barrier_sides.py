"""PerimeterBarrier.sides — cardinal Facing list; invalid entries reject atomically."""

from __future__ import annotations

from app.application.jsonValidation.resolve import UnresolvedModelError, ResolveContext, resolve_result
import unittest

from app.application.jsonValidation.resolve import resolve_model
from app.dataModel.locations.settlement.area.perimeterBarrier import (
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

    def test_intercardinal_and_unknown_reject_whole_field(self):
        for sides in (["north", "north_east", "south"], ["north", "nope"], ["north_east", "nope"]):
            with self.subTest(sides=sides):
                result = resolve_result(PerimeterBarrier, {"sides": sides},
                                        ctx=ResolveContext(validate_only=True))
                self.assertFalse(result.resolved)
                self.assertEqual(result.issues[0].path, ("sides",))

    def test_dedupe_preserves_order(self) -> None:
        barrier = PerimeterBarrier(sides=["east", "north", "east"])
        self.assertEqual(barrier.sides, [Facing.EAST, Facing.NORTH])

    def test_resolve_non_list_rejects(self):
        with self.assertLogs("app.application.jsonValidation.resolve", "WARNING") as logs:
            result = resolve_result(PerimeterBarrier, {"template": "stone_fence", "sides": "north"})
        self.assertFalse(result.resolved)
        self.assertEqual(result.issues[0].path, ("sides",))
        self.assertIn("WarningError", logs.output[0])

    def test_resolve_mixed_list_rejects_without_filtering(self):
        with self.assertRaises(UnresolvedModelError):
            resolve_model(PerimeterBarrier, {"sides": ["west", "nope", "south"]})


if __name__ == "__main__":
    unittest.main()
