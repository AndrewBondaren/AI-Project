"""pack_cell_slots — pair rules, not mill leftover / dump glyphs."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.application.worldData.generators.terrain.relief.validate.gradeCellRays import (
    validate_grade_cell_slots,
)
from app.application.worldData.pack.refine.gradeCellSlots import pack_cell_slots
from app.dataModel.terrain.relief.gradeSlot import (
    GradeCouple,
    GradeOctant,
    GradeSeam,
    GradeSheer,
)
from app.dataModel.terrain.relief.reliefSlopeGeom import angle_from_height_length


def _by_cell(z: dict[tuple[int, int], int]) -> dict[tuple[int, int], tuple[int, ...]]:
    return {c.cell: c.slots for c in pack_cell_slots(z)}


class TestPackCellSlotsPit(unittest.TestCase):
    def test_pit_four_around_two_matches_sot_codes(self) -> None:
        z = {
            (x, y): (2 if (x, y) == (1, 1) else 4)
            for x in range(3)
            for y in range(3)
        }
        slots = _by_cell(z)
        seam, couple = int(GradeSeam.SEAM), int(GradeCouple.COUPLE)
        east = int(GradeOctant.EAST)
        self.assertEqual(
            slots[(0, 1)],
            (seam, couple, couple, seam, east, seam, couple, couple),
        )
        self.assertEqual(slots[(1, 1)][3], east)
        self.assertEqual(
            slots[(1, 1)],
            (
                int(GradeOctant.SOUTHEAST),
                int(GradeOctant.SOUTH),
                int(GradeOctant.SOUTHWEST),
                int(GradeOctant.EAST),
                int(GradeOctant.WEST),
                int(GradeOctant.NORTHEAST),
                int(GradeOctant.NORTH),
                int(GradeOctant.NORTHWEST),
            ),
        )
        self.assertEqual(slots[(1, 2)][6], int(GradeOctant.SOUTH))
        theta = angle_from_height_length(2, 1)
        self.assertLess(theta, 80.0)
        self.assertNotIn(int(GradeSheer.SHEER), slots[(1, 1)])

    def test_pool_east_flow_same_on_both_ends(self) -> None:
        z = {(x, y): 4 - x for x in range(3) for y in range(3)}
        slots = _by_cell(z)
        east = int(GradeOctant.EAST)
        self.assertEqual(slots[(0, 2)][4], east)
        self.assertEqual(slots[(1, 2)][3], east)
        self.assertEqual(slots[(0, 2)][0], int(GradeSeam.SEAM))

    def test_l1_dz6_is_sheer_not_octant(self) -> None:
        z = {(0, 0): 6, (1, 0): 0}
        slots = _by_cell(z)
        self.assertEqual(slots[(0, 0)][4], int(GradeSheer.SHEER))
        self.assertEqual(slots[(1, 0)][3], int(GradeSheer.SHEER))


class TestValidateGradeCellSlots(unittest.TestCase):
    def test_complete_occupancy_is_clean_missing_cell_errors(self) -> None:
        z = {(0, 0): 4, (1, 0): 4}
        packed = pack_cell_slots(z)
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            n_empty = validate_grade_cell_slots(z, packed, z_height_map=z)
        err.assert_not_called()
        self.assertEqual(n_empty, 0)
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            n_empty = validate_grade_cell_slots(z, packed[:1], z_height_map=z)
        self.assertEqual(err.call_count, 1)
        self.assertEqual(n_empty, 1)


if __name__ == "__main__":
    unittest.main()
