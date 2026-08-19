"""3×3 grade consume dump — Facing slots, W alignment, leftover rays not column facing."""

from __future__ import annotations

import unittest

from app.application.worldData.render.fineTerrainAsciiKernel import draw_grade_consume_grid
from app.application.worldData.render.gradeRayDump import (
    GradeRayIndex,
    compose_grade_cell,
    facing_cell_slot,
)
from app.application.worldData.render.mapSymbols import (
    GRADE_CELL_INNER_WIDTH,
    GRADE_SHEER_SYMBOL,
    format_glyph_field,
    format_height_cell,
    paired_height_cell_width,
)
from app.dataModel.spatial.facing import Facing, GRID_OUTWARD_DELTA
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainColumnWire, FineTerrainZRun


class TestGradeRayDump(unittest.TestCase):
    def test_slots_follow_grid_outward_delta(self) -> None:
        self.assertEqual(facing_cell_slot(Facing.NORTH), (0, 1))
        self.assertEqual(facing_cell_slot(Facing.SOUTH), (2, 1))
        self.assertEqual(facing_cell_slot(Facing.WEST), (1, 0))
        self.assertEqual(facing_cell_slot(Facing.EAST), (1, 2))
        self.assertEqual(facing_cell_slot(Facing.NORTHWEST), (0, 0))
        self.assertEqual(facing_cell_slot(Facing.NORTHEAST), (0, 2))
        self.assertEqual(facing_cell_slot(Facing.SOUTHWEST), (2, 0))
        self.assertEqual(facing_cell_slot(Facing.SOUTHEAST), (2, 2))
        for facing, (dx, dy) in GRID_OUTWARD_DELTA.items():
            row, col = facing_cell_slot(facing)
            self.assertEqual((row, col), (1 - dy, 1 + dx))

    def test_compose_center_always_and_sheer_on_facing_slot(self) -> None:
        top, mid, bot = compose_grade_cell(
            "_",
            {Facing.SOUTH: ReliefSideKind.SHEER},
        )
        self.assertEqual(top, "   ")
        self.assertEqual(mid, " _ ")
        self.assertEqual(bot, f" {GRADE_SHEER_SYMBOL} ")
        self.assertEqual(len(top), GRADE_CELL_INNER_WIDTH)

    def test_slope_arrow_on_east_slot(self) -> None:
        _top, mid, _bot = compose_grade_cell(
            "_",
            {Facing.EAST: ReliefSideKind.SLOPE},
        )
        self.assertEqual(mid, " _→")

    def test_glyph_field_matches_height_pad(self) -> None:
        width = paired_height_cell_width([4, 6, 3])
        self.assertEqual(width, 3)
        z_cell = format_height_cell(6, width=width)
        glyph = format_glyph_field(".#.", width=width)
        self.assertEqual(len(z_cell), len(glyph))
        self.assertEqual(len(z_cell), 3)

    def test_draw_omits_without_uid_or_rays(self) -> None:
        cols = {
            (0, 0): FineTerrainColumnWire(
                lx=0, ly=0,
                runs=[FineTerrainZRun(z0=0, z1=1, system_terrain="plains")],
            ),
        }
        self.assertEqual(
            draw_grade_consume_grid(cols, GradeRayIndex(), title="t"),
            "",
        )

    def test_draw_uses_leftover_not_column_facing(self) -> None:
        cols = {
            (0, 0): FineTerrainColumnWire(
                lx=0, ly=0,
                runs=[FineTerrainZRun(z0=0, z1=4, system_terrain="plains")],
                system_grade_uid="g1",
                system_facing="east",
            ),
        }
        empty_edges = draw_grade_consume_grid(cols, GradeRayIndex(), title="t")
        self.assertIn("_", empty_edges)
        self.assertNotIn("→", empty_edges)
        rays = GradeRayIndex((
            GradeRimRay(x=0, y=0, facing=Facing.SOUTH, kind=ReliefSideKind.SHEER),
        ))
        with_ray = draw_grade_consume_grid(cols, rays, title="t")
        self.assertIn(GRADE_SHEER_SYMBOL, with_ray)
        mid = [ln for ln in with_ray.splitlines() if ln.startswith("   0 |")]
        self.assertEqual(len(mid), 1)
        self.assertIn("_", mid[0])
        self.assertNotIn(GRADE_SHEER_SYMBOL, mid[0])


if __name__ == "__main__":
    unittest.main()
