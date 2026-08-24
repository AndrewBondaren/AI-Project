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
    GRADE_COUPLE_SYMBOL,
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

    def test_couple_plus_and_pack_ray_wins(self) -> None:
        top, mid, bot = compose_grade_cell(
            "_",
            {
                Facing.SOUTH: ReliefSideKind.SHEER,
                Facing.EAST: ReliefSideKind.COUPLE,
            },
        )
        self.assertEqual(top, "   ")
        self.assertEqual(mid, f" _{GRADE_COUPLE_SYMBOL}")
        self.assertEqual(bot, f" {GRADE_SHEER_SYMBOL} ")

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

    def test_draw_paints_sender_and_receiver_slots(self) -> None:
        cols = {
            (0, 1): FineTerrainColumnWire(
                lx=0, ly=1,
                runs=[FineTerrainZRun(z0=0, z1=10, system_terrain="plains")],
            ),
            (0, 0): FineTerrainColumnWire(
                lx=0, ly=0,
                runs=[FineTerrainZRun(z0=0, z1=4, system_terrain="plains")],
            ),
        }
        sender = GradeRimRay(x=0, y=1, facing=Facing.SOUTH, kind=ReliefSideKind.SHEER)
        recv = GradeRimRay(x=0, y=0, facing=Facing.NORTH, kind=ReliefSideKind.SHEER)
        body = draw_grade_consume_grid(
            cols,
            GradeRayIndex((sender, recv)),
            title="t",
        )
        self.assertEqual(body.count(GRADE_SHEER_SYMBOL), 2)

    def test_draw_equal_z_does_not_invent_plus(self) -> None:
        cols = {
            (0, 0): FineTerrainColumnWire(
                lx=0, ly=0,
                runs=[FineTerrainZRun(z0=0, z1=4, system_terrain="plains")],
                system_grade_uid="g1",
            ),
            (1, 0): FineTerrainColumnWire(
                lx=1, ly=0,
                runs=[FineTerrainZRun(z0=0, z1=4, system_terrain="plains")],
            ),
        }
        body = draw_grade_consume_grid(cols, GradeRayIndex(), title="t")
        self.assertNotIn(GRADE_COUPLE_SYMBOL, body)

    def test_draw_plus_from_pack_couple(self) -> None:
        cols = {
            (0, 0): FineTerrainColumnWire(
                lx=0, ly=0,
                runs=[FineTerrainZRun(z0=0, z1=4, system_terrain="plains")],
                system_grade_uid="g1",
            ),
            (1, 0): FineTerrainColumnWire(
                lx=1, ly=0,
                runs=[FineTerrainZRun(z0=0, z1=4, system_terrain="plains")],
            ),
        }
        rays = GradeRayIndex((
            GradeRimRay(x=0, y=0, facing=Facing.EAST, kind=ReliefSideKind.COUPLE),
            GradeRimRay(x=1, y=0, facing=Facing.WEST, kind=ReliefSideKind.COUPLE),
        ))
        body = draw_grade_consume_grid(cols, rays, title="t")
        self.assertIn(GRADE_COUPLE_SYMBOL, body)
        self.assertNotIn(GRADE_SHEER_SYMBOL, body)

    def test_z_slice_omits_pack_couple(self) -> None:
        cols = {
            (0, 0): FineTerrainColumnWire(
                lx=0, ly=0,
                runs=[FineTerrainZRun(z0=0, z1=4, system_terrain="plains")],
                system_grade_uid="g1",
            ),
            (1, 0): FineTerrainColumnWire(
                lx=1, ly=0,
                runs=[FineTerrainZRun(z0=0, z1=4, system_terrain="plains")],
            ),
        }
        rays = GradeRayIndex((
            GradeRimRay(x=0, y=0, facing=Facing.EAST, kind=ReliefSideKind.COUPLE),
            GradeRimRay(x=1, y=0, facing=Facing.WEST, kind=ReliefSideKind.COUPLE),
        ))
        body = draw_grade_consume_grid(
            cols, rays, title="t", surface_z=4,
        )
        self.assertNotIn(GRADE_COUPLE_SYMBOL, body)


if __name__ == "__main__":
    unittest.main()
