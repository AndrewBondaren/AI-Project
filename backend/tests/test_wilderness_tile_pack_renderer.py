"""WildernessTilePackRenderer + FineTerrainAsciiKernel unit tests."""

import unittest

from app.application.worldData.render.fineTerrainAsciiKernel import (
    symbols_surface_top,
    top_terrain,
)
from app.application.worldData.render.renderPayloads import LEVEL_SURFACE
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

        levels = renderer.render_all_levels(include_z_slices=False)
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


if __name__ == "__main__":
    unittest.main()
