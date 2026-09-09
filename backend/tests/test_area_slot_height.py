"""AreaSlot.height — sum of floor spans above ground_z."""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import (
    height_from_levels,
    z_deep_from_levels,
)
from app.dataModel.worldPack.settlementStructureWire import AreaSlotWire
from app.dataModel.spatial.facing import Facing


@dataclass
class _Level:
    z: int
    z_height: int


class TestParcelHeight(unittest.TestCase):
    def test_ground_floor_full_z_height(self) -> None:
        self.assertEqual(
            height_from_levels(0, [_Level(z=0, z_height=3)]),
            3,
        )

    def test_two_storeys_sum(self) -> None:
        self.assertEqual(
            height_from_levels(0, [
                _Level(z=0, z_height=3),
                _Level(z=3, z_height=3),
            ]),
            6,
        )

    def test_basement_below_ground_is_zero_height(self) -> None:
        levels = [_Level(z=-2, z_height=2)]
        self.assertEqual(height_from_levels(0, levels), 0)
        self.assertEqual(z_deep_from_levels(0, levels), 2)

    def test_floor_straddling_splits_without_sharing_ground(self) -> None:
        levels = [_Level(z=-1, z_height=3)]
        self.assertEqual(height_from_levels(0, levels), 2)
        self.assertEqual(z_deep_from_levels(0, levels), 1)
        self.assertEqual(
            height_from_levels(0, levels) + z_deep_from_levels(0, levels),
            3,
        )

    def test_ground_floor_has_no_z_deep(self) -> None:
        levels = [_Level(z=0, z_height=3)]
        self.assertEqual(height_from_levels(0, levels), 3)
        self.assertEqual(z_deep_from_levels(0, levels), 0)

    def test_no_levels_is_zero(self) -> None:
        self.assertEqual(height_from_levels(5, ()), 0)
        self.assertEqual(z_deep_from_levels(5, ()), 0)

    def test_wire_omits_height_and_z_deep_defaults_zero(self) -> None:
        slot = AreaSlotWire(cells=[(0, 0)], ground_z=4, facing=Facing.SOUTH)
        self.assertEqual(slot.height, 0)
        self.assertEqual(slot.z_deep, 0)


if __name__ == "__main__":
    unittest.main()
