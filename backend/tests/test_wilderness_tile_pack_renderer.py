"""WildernessTilePackRenderer + FineTerrainAsciiKernel unit tests."""

import unittest

from app.application.worldData.render.fineTerrainAsciiKernel import (
    column_diagnostics_summary,
    column_span,
    symbols_by_occupied_z,
    symbols_surface_top,
    top_terrain,
    values_cliff_delta,
    z_occupied,
)
from app.application.worldData.render.renderPayloads import (
    LEVEL_CLIFF_DELTA,
    LEVEL_COLUMN_SPAN,
    LEVEL_SURFACE,
)
from app.application.worldData.render.wildernessTilePackRenderer import WildernessTilePackRenderer
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
        self.assertIn(".", surface)  # plains
        self.assertIn("f", surface)  # forest
        self.assertIn("~", surface)  # liquid
        # tile-local x: chunk0 → 0,1; chunk1 → 2
        self.assertIn("tile-local grid", surface)

        levels = renderer.render_all_levels(
            include_z_slices=False,
            include_column_diagnostics=False,
        )
        self.assertEqual(list(levels.keys()), [LEVEL_SURFACE])

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

        sparse = renderer.render_occupied_z_levels_sparse()
        self.assertEqual(sorted(sparse), [1, 2, 3])
        self.assertIn("format=sparse_xy", sparse[2])
        self.assertIn("0\t0\tm", sparse[2])  # x=0 y=0 mountain at z=2


if __name__ == "__main__":
    unittest.main()
