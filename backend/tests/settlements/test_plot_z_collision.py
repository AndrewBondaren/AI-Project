"""Plot xy×z collision gated on multiple district decks (ярусы)."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.planner.plotCollision import (
    district_has_multiple_decks,
    plot_z_collisions,
    plots_overlap_z,
)
from app.dataModel.spatial.facing import Facing


def _slot(
    *,
    cells: list[tuple[int, int]],
    ground_z: int = 0,
    height: int = 0,
    z_deep: int = 0,
    deck: int = 0,
) -> AreaSlot:
    return AreaSlot(
        cells=cells,
        ground_z=ground_z,
        facing=Facing.SOUTH,
        height=height,
        z_deep=z_deep,
        deck=deck,
    )


class TestPlotZCollision(unittest.TestCase):
    def test_single_deck_skips_even_if_xy_and_z_overlap(self) -> None:
        cells = [(0, 0), (1, 0)]
        slots = [
            _slot(cells=cells, height=4),
            _slot(cells=cells, height=4),
        ]
        self.assertFalse(district_has_multiple_decks(slots))
        self.assertEqual(plot_z_collisions(slots), [])

    def test_stacked_decks_no_z_overlap_ok(self) -> None:
        cells = [(0, 0)]
        low = _slot(cells=cells, ground_z=0, height=6, deck=0)
        high = _slot(cells=cells, ground_z=6, height=3, deck=1)
        self.assertTrue(district_has_multiple_decks([low, high]))
        self.assertFalse(plots_overlap_z(low, high))
        self.assertEqual(plot_z_collisions([low, high]), [])

    def test_stacked_decks_z_overlap_hits(self) -> None:
        cells = [(0, 0)]
        low = _slot(cells=cells, ground_z=0, height=6, deck=0)
        high = _slot(cells=cells, ground_z=5, height=3, deck=1)
        self.assertEqual(plot_z_collisions([low, high]), [(0, 1)])

    def test_multi_deck_disjoint_xy_skips_z(self) -> None:
        low = _slot(cells=[(0, 0)], ground_z=0, height=6, deck=0)
        high = _slot(cells=[(9, 9)], ground_z=0, height=6, deck=1)
        self.assertEqual(plot_z_collisions([low, high]), [])

    def test_basement_overlap_with_surface(self) -> None:
        cells = [(0, 0)]
        surface = _slot(cells=cells, ground_z=0, height=3, z_deep=0, deck=0)
        under = _slot(cells=cells, ground_z=0, height=0, z_deep=2, deck=-1)
        self.assertEqual(plot_z_collisions([surface, under]), [])
        under_into = _slot(cells=cells, ground_z=1, height=0, z_deep=3, deck=-1)
        self.assertEqual(plot_z_collisions([surface, under_into]), [(0, 1)])


if __name__ == "__main__":
    unittest.main()
