"""pack_cell_slots — pair rules, not mill leftover / dump glyphs."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.application.worldData.generators.terrain.relief.validate.gradeCellSlotValidate import (
    validate_grade_cell_slots,
)
from app.application.worldData.pack.refine.gradeCellSlots import pack_cell_slots
from app.dataModel.spatial.facing import Facing, OPPOSITE
from app.dataModel.terrain.relief.gradeLeftoverPair import (
    LEFTOVER_PAIR_LENGTH_CELLS,
    LEFTOVER_SHEER_MIN_DEG,
    leftover_pair_theta,
)
from app.dataModel.terrain.relief.gradeSlot import (
    GRADE_SLOT_SCHEMA_ID,
    GradeCouple,
    GradeOctant,
    GradeSeam,
    GradeSheer,
    GradeSlotSidecar,
    decode_grade_slot_code,
    facing_from_octant,
    octant_from_facing,
)


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
        theta = leftover_pair_theta(2)
        self.assertLess(theta, LEFTOVER_SHEER_MIN_DEG)
        self.assertEqual(LEFTOVER_PAIR_LENGTH_CELLS, 1)
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
            "app.application.worldData.generators.terrain.relief.validate.gradeCellSlotValidate.relief_error",
        ) as err:
            n_empty = validate_grade_cell_slots(z, packed, z_height_map=z)
        err.assert_not_called()
        self.assertEqual(n_empty, 0)
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellSlotValidate.relief_error",
        ) as err:
            n_empty = validate_grade_cell_slots(z, packed[:1], z_height_map=z)
        self.assertEqual(err.call_count, 1)
        self.assertEqual(n_empty, 1)


class TestGradeSlotWire(unittest.TestCase):
    def test_octant_opposite_matches_facing(self) -> None:
        for facing in Facing:
            octant = octant_from_facing(facing)
            self.assertEqual(octant.opposite(), octant_from_facing(OPPOSITE[facing]))
            self.assertEqual(facing_from_octant(octant), facing)

    def test_decode_uses_enum_members(self) -> None:
        self.assertIs(decode_grade_slot_code(GradeOctant.EAST), GradeOctant.EAST)
        self.assertIs(decode_grade_slot_code(GradeSeam.SEAM), GradeSeam.SEAM)
        self.assertIs(decode_grade_slot_code(GradeSheer.SHEER), GradeSheer.SHEER)
        self.assertIs(decode_grade_slot_code(GradeCouple.COUPLE), GradeCouple.COUPLE)
        with self.assertRaises(ValueError):
            decode_grade_slot_code(11)

    def test_sidecar_schema_id_is_sot_constant(self) -> None:
        body = GradeSlotSidecar()
        self.assertEqual(body.schema_id, GRADE_SLOT_SCHEMA_ID)
        with self.assertRaises(ValidationError):
            GradeSlotSidecar(schema_id="SCH-GRADE-RAY-SIDECAR")


class TestGradeSlotValidateGate(unittest.TestCase):
    def test_env_off_by_default_on_for_dev_flag(self) -> None:
        from app.application.worldData.generators.terrain.relief.validate.gradeCellSlotValidate import (
            DEBUG_GRADE_SLOT_VALIDATE_ENV,
            grade_slot_validate_enabled,
        )

        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop(DEBUG_GRADE_SLOT_VALIDATE_ENV, None)
            self.assertFalse(grade_slot_validate_enabled())
        with patch.dict("os.environ", {DEBUG_GRADE_SLOT_VALIDATE_ENV: "1"}):
            self.assertTrue(grade_slot_validate_enabled())
        with patch.dict("os.environ", {DEBUG_GRADE_SLOT_VALIDATE_ENV: "0"}):
            self.assertFalse(grade_slot_validate_enabled())


if __name__ == "__main__":
    unittest.main()
