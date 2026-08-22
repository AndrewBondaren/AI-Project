"""WildernessTilePackRenderer + FineTerrainAsciiKernel unit tests."""

import unittest

from app.application.worldData.render.fineTerrainAsciiKernel import (
    column_diagnostics_summary,
    column_span,
    symbols_by_occupied_z,
    symbols_surface_top,
    top_terrain,
    values_cliff_delta,
    values_surface_z,
    z_occupied,
)
from app.application.worldData.render.renderPayloads import (
    LEVEL_CLIFF_DELTA,
    LEVEL_COLUMN_SPAN,
    LEVEL_SURFACE,
    LEVEL_SURFACE_GRADE,
    LEVEL_SURFACE_Z,
)
from app.application.worldData.render.gradeRayDump import GradeRayIndex
from app.application.worldData.render.wildernessTilePackRenderer import WildernessTilePackRenderer
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay
from app.dataModel.worldPack.fineTerrainChunkWire import (
    FineTerrainChunkWire,
    FineTerrainColumnWire,
    FineTerrainZRun,
)


class TestWildernessTilePackRenderer(unittest.TestCase):
    def test_mosaic_joins_chunks_by_cx_cy(self) -> None:
        chunks = [
            FineTerrainChunkWire(
                cx=0,
                cy=0,
                chunk_columns=2,
                columns=[
                    FineTerrainColumnWire(
                        lx=0,
                        ly=0,
                        runs=[FineTerrainZRun(z0=0, z1=1, system_terrain="plains")],
                    ),
                    FineTerrainColumnWire(
                        lx=1,
                        ly=0,
                        runs=[FineTerrainZRun(z0=0, z1=2, system_terrain="forest")],
                    ),
                ],
            ),
            FineTerrainChunkWire(
                cx=1,
                cy=0,
                chunk_columns=2,
                columns=[
                    FineTerrainColumnWire(
                        lx=0,
                        ly=0,
                        runs=[FineTerrainZRun(z0=1, z1=3, system_terrain="liquid_body")],
                    ),
                ],
            ),
        ]
        renderer = WildernessTilePackRenderer(
            chunks,
            tile_gx=-2,
            tile_gy=-2,
            tile_size_m=1000,
        )
        self.assertEqual(renderer.column_count, 3)
        surface = renderer.render_surface_top()
        self.assertIn("wilderness tile=(-2,-2)", surface)
        self.assertIn("pack wilderness_chunk mosaic", surface)
        self.assertIn("_", surface)  # plains
        self.assertIn("f", surface)  # forest
        self.assertIn("~", surface)  # liquid
        # tile-local x: chunk0 → 0,1; chunk1 → 2
        self.assertIn("tile-local grid", surface)

        levels = renderer.render_all_levels(
            include_z_slices=False,
            include_column_diagnostics=False,
        )
        self.assertEqual(list(levels.keys()), [LEVEL_SURFACE, LEVEL_SURFACE_Z])

        at_z2 = renderer.render_level(2)
        self.assertIn("z=2", at_z2)
        self.assertIn("f", at_z2)
        self.assertIn("~", at_z2)

    def test_kernel_top_terrain(self) -> None:
        col = FineTerrainColumnWire(
            lx=0,
            ly=0,
            runs=[
                FineTerrainZRun(z0=0, z1=1, system_terrain="plains"),
                FineTerrainZRun(z0=2, z1=4, system_terrain="forest"),
            ],
        )
        self.assertEqual(top_terrain(col), (4, "forest"))
        self.assertEqual(values_surface_z({(0, 0): col}), {(0, 0): 4})
        syms = symbols_surface_top({(0, 0): col})
        self.assertEqual(syms[(0, 0)], "f")

    def test_dense_z_and_column_diagnostics_expose_thin_steep_gap(self) -> None:
        # Thick wall column (span 3) next to thin top-only neighbor with Δz=2.
        chunks = [
            FineTerrainChunkWire(
                cx=0,
                cy=0,
                chunk_columns=2,
                columns=[
                    FineTerrainColumnWire(
                        lx=0,
                        ly=0,
                        runs=[FineTerrainZRun(z0=1, z1=3, system_terrain="mountain")],
                    ),
                    FineTerrainColumnWire(
                        lx=1,
                        ly=0,
                        runs=[FineTerrainZRun(z0=1, z1=1, system_terrain="plains")],
                    ),
                ],
            ),
        ]
        thick = chunks[0].columns[0]
        thin = chunks[0].columns[1]
        self.assertEqual(column_span(thick), 3)
        self.assertEqual(column_span(thin), 1)
        self.assertEqual(z_occupied([thick]), [1, 2, 3])

        cols = {(0, 0): thick, (1, 0): thin}
        deltas = values_cliff_delta(cols)
        self.assertEqual(deltas[(0, 0)], 2)
        self.assertEqual(deltas[(1, 0)], 2)
        summary = column_diagnostics_summary(cols)
        self.assertIn("thin_steep_gap_suspect=1", summary)

        renderer = WildernessTilePackRenderer(
            chunks, tile_gx=0, tile_gy=0, tile_size_m=1000,
        )
        levels = renderer.render_all_levels(
            include_z_slices=True,
            include_column_diagnostics=True,
        )
        self.assertIn(LEVEL_SURFACE, levels)
        self.assertIn(LEVEL_SURFACE_Z, levels)
        self.assertIn(LEVEL_COLUMN_SPAN, levels)
        self.assertIn(LEVEL_CLIFF_DELTA, levels)
        self.assertIn("thin_steep_gap_suspect=", levels[LEVEL_COLUMN_SPAN])
        # Dense mid-band z=2 present (endpoints-only would skip if only ends mattered).
        self.assertIn("2", levels)
        self.assertIn("m", levels["2"])

        by_z = symbols_by_occupied_z(cols)
        self.assertEqual(sorted(by_z), [1, 2, 3])
        self.assertIn((0, 0), by_z[2])
        self.assertNotIn((1, 0), by_z[2])  # thin column only at z=1

        occupied_ascii = renderer.render_occupied_z_levels()
        self.assertEqual(sorted(occupied_ascii), [1, 2, 3])
        self.assertIn("m", occupied_ascii[2])
        # Shared mosaic frame: z=2 only has thick col, but x span includes thin neighbor.
        row2 = [ln for ln in occupied_ascii[2].splitlines() if ln.startswith("   0 |")]
        self.assertEqual(len(row2), 1)
        self.assertEqual(row2[0], "   0 |m |")
        row1 = [ln for ln in occupied_ascii[1].splitlines() if ln.startswith("   0 |")]
        self.assertEqual(row1[0], "   0 |m_|")
        # Same grid width on every z (no shift).
        self.assertEqual(len(row1[0]), len(row2[0]))
        self.assertIn("tile-local grid gx: 0..1", occupied_ascii[2])

        sparse = dict(renderer.iter_occupied_z_sparse())
        self.assertEqual(sorted(sparse), [1, 2, 3])
        self.assertIn("format=sparse_xy", sparse[2])
        self.assertIn("0\t0\tm", sparse[2])
        self.assertNotIn("1\t0\t", sparse[2])
        self.assertIn("0\t0\tm", sparse[1])
        self.assertIn("1\t0\t_", sparse[1])

    def test_surface_grade_and_grade_at_z(self) -> None:
        chunks = [
            FineTerrainChunkWire(
                cx=0,
                cy=0,
                chunk_columns=2,
                columns=[
                    FineTerrainColumnWire(
                        lx=0,
                        ly=0,
                        runs=[FineTerrainZRun(z0=0, z1=3, system_terrain="plains")],
                        system_grade_uid="g1",
                        system_facing="east",
                    ),
                    FineTerrainColumnWire(
                        lx=1,
                        ly=0,
                        runs=[FineTerrainZRun(z0=0, z1=1, system_terrain="forest")],
                    ),
                ],
            ),
        ]
        renderer = WildernessTilePackRenderer(
            chunks, tile_gx=1, tile_gy=2, tile_size_m=1000,
            ray_index=GradeRayIndex((
                GradeRimRay(
                    x=1000, y=2000, facing=Facing.EAST, kind=ReliefSideKind.SLOPE,
                ),
            )),
        )
        levels = renderer.render_all_levels(
            include_z_slices=False,
            include_column_diagnostics=False,
        )
        self.assertIn(LEVEL_SURFACE, levels)
        self.assertIn(LEVEL_SURFACE_GRADE, levels)
        self.assertIn("→", levels[LEVEL_SURFACE_GRADE])
        self.assertIn("f", levels[LEVEL_SURFACE_GRADE])  # forest center
        mid = [
            ln for ln in levels[LEVEL_SURFACE_GRADE].splitlines()
            if ln.startswith("   0 |")
        ]
        self.assertEqual(len(mid), 1)
        self.assertIn("→", mid[0])
        self.assertEqual(renderer.render_grade_at_z(1), "")
        grade3 = renderer.render_grade_at_z(3)
        self.assertIn("→", grade3)
        self.assertIn("_", grade3)
        pairs = list(renderer.iter_grade_z_levels_aligned())
        self.assertEqual([z for z, _ in pairs], [3])


    def test_grade_at_z_crop_empty_shrinks_frame(self) -> None:
        columns = [
            FineTerrainColumnWire(
                lx=0,
                ly=0,
                runs=[FineTerrainZRun(z0=0, z1=5, system_terrain="plains")],
                system_grade_uid="g1",
                system_facing="east",
            ),
        ]
        columns.extend(
            FineTerrainColumnWire(
                lx=x,
                ly=0,
                runs=[FineTerrainZRun(z0=0, z1=1, system_terrain="forest")],
            )
            for x in range(1, 8)
        )
        chunks = [
            FineTerrainChunkWire(cx=0, cy=0, chunk_columns=8, columns=columns),
        ]
        renderer = WildernessTilePackRenderer(
            chunks, tile_gx=0, tile_gy=0, tile_size_m=1000,
        )
        mosaic = renderer.render_grade_at_z(5)
        cropped = renderer.render_grade_at_z(5, crop_empty=True)
        self.assertIn("_", cropped)
        self.assertLess(len(cropped), len(mosaic))
        self.assertIn("tile-local grid gx: 0..1", cropped)
        self.assertIn("tile-local grid gx: 0..7", mosaic)


if __name__ == "__main__":
    unittest.main()
