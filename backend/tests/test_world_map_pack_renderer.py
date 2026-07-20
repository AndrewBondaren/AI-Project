"""WorldMapPackRenderer unit tests — pack L0 wire path."""

import unittest

from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.worldMapPackRenderer import (
    WorldMapPackRenderer,
    wire_symbol,
)
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


class TestWorldMapPackRenderer(unittest.TestCase):
    def test_wire_symbol_hydrology_and_terrain(self):
        river = WorldMapCellWire(
            tx=0, ty=0, surface_z=1,
            system_terrain="plains",
            hydrology_role=WorldMapHydrologyRole.RIVER,
        )
        plains = WorldMapCellWire(tx=1, ty=0, surface_z=1, system_terrain="plains")
        ravine = WorldMapCellWire(tx=2, ty=0, surface_z=1, system_terrain="ravine")
        mountain = WorldMapCellWire(tx=3, ty=0, surface_z=1, system_terrain="mountain")
        unmapped = WorldMapCellWire(tx=4, ty=0, surface_z=1, system_terrain="crevice")
        self.assertEqual(wire_symbol(river), "y")
        self.assertEqual(wire_symbol(plains), ".")
        self.assertEqual(wire_symbol(ravine), "v")
        self.assertEqual(wire_symbol(mountain), "m")
        self.assertEqual(wire_symbol(unmapped), " ")

    def test_macro_and_light_grid_with_pin(self):
        cells = {
            (0, 0): WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains"),
            (1, 0): WorldMapCellWire(
                tx=1, ty=0, surface_z=1,
                system_terrain="plains",
                hydrology_role=WorldMapHydrologyRole.SEA,
            ),
            (0, 1): WorldMapCellWire(tx=0, ty=1, surface_z=1, system_terrain="forest"),
            (1, 1): WorldMapCellWire(tx=1, ty=1, surface_z=1, system_terrain="plains"),
        }
        tile = PackTileLightView(gx=0, gy=0, side=2, cells=cells)
        pins = LocationsIndexWire(
            locations=[
                LocationsIndexPin(
                    location_uid="loc-a",
                    map_x=1500,
                    map_y=1500,
                    display_name="A",
                ),
            ],
        )
        renderer = WorldMapPackRenderer([tile], tile_size_m=3000, pins=pins)
        macro = renderer.render_macro(mark_location=True)
        self.assertIn("@", macro)
        self.assertIn("MACRO AGGREGATE", macro)
        light = renderer.render_tile_light_grid(0, 0, mark_location=True)
        self.assertIn("~", light)
        self.assertIn("f", light)
        self.assertIn("@", light)
        self.assertIn("pack L0 light grid 2×2", light)
        mosaic = renderer.render_light_mask_mosaic(mark_location=True)
        self.assertIn("pack L0 light mosaic", mosaic)
        self.assertNotIn("tile Gx=", mosaic)
        self.assertIn("~", mosaic)
        self.assertIn("@", mosaic)

    def test_light_mask_mosaic_unmapped_tiles_are_spaces(self):
        """MLB-12: frame larger than baked set → spaces, not crop to baked only."""
        tile = PackTileLightView(
            gx=0,
            gy=0,
            side=2,
            cells={
                (0, 0): WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains"),
                (1, 0): WorldMapCellWire(tx=1, ty=0, surface_z=1, system_terrain="plains"),
                (0, 1): WorldMapCellWire(tx=0, ty=1, surface_z=1, system_terrain="plains"),
                (1, 1): WorldMapCellWire(tx=1, ty=1, surface_z=1, system_terrain="mountain"),
            },
        )
        mosaic = WorldMapPackRenderer(
            [tile], tile_size_m=3000,
        ).render_light_mask_mosaic(gx0=-1, gy0=0, gx1=0, gy1=0)
        self.assertIn("macro Gx-1..Gx0 Gy0..Gy0", mosaic)
        # left macro-tile unmapped (2 spaces) + right tile "..m" on y=1 / ".." on y=0
        self.assertIn("   0 |  ..|", mosaic)
        self.assertIn("   1 |  .m|", mosaic)

    def test_light_mask_mosaic_stitches_adjacent_tiles(self):
        """Adjacent macro-tiles form one matrix — rivers continue across the seam."""
        left = PackTileLightView(
            gx=0,
            gy=0,
            side=2,
            cells={
                (0, 0): WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains"),
                (1, 0): WorldMapCellWire(
                    tx=1, ty=0, surface_z=1, system_terrain="plains",
                    hydrology_role=WorldMapHydrologyRole.RIVER,
                ),
                (0, 1): WorldMapCellWire(tx=0, ty=1, surface_z=1, system_terrain="plains"),
                (1, 1): WorldMapCellWire(tx=1, ty=1, surface_z=1, system_terrain="plains"),
            },
        )
        right = PackTileLightView(
            gx=1,
            gy=0,
            side=2,
            cells={
                (0, 0): WorldMapCellWire(
                    tx=0, ty=0, surface_z=1, system_terrain="plains",
                    hydrology_role=WorldMapHydrologyRole.RIVER,
                ),
                (1, 0): WorldMapCellWire(tx=1, ty=0, surface_z=1, system_terrain="plains"),
                (0, 1): WorldMapCellWire(tx=0, ty=1, surface_z=1, system_terrain="plains"),
                (1, 1): WorldMapCellWire(tx=1, ty=1, surface_z=1, system_terrain="forest"),
            },
        )
        mosaic = WorldMapPackRenderer(
            [left, right], tile_size_m=3000,
        ).render_light_mask_mosaic()
        # y=0: . r | r .  → ".yy."
        # y=1: . . | . f  → "...f"
        self.assertIn("   0 |.yy.|", mosaic)
        self.assertIn("   1 |...f|", mosaic)
        self.assertNotIn("tile Gx=", mosaic)

    def test_light_height_mosaic_pads_to_widest_z(self):
        cells = {
            (0, 0): WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains"),
            (1, 0): WorldMapCellWire(tx=1, ty=0, surface_z=12, system_terrain="mountain"),
            (0, 1): WorldMapCellWire(tx=0, ty=1, surface_z=-3, system_terrain="plains"),
            (1, 1): WorldMapCellWire(tx=1, ty=1, surface_z=7, system_terrain="plains"),
        }
        tile = PackTileLightView(gx=0, gy=0, side=2, cells=cells)
        renderer = WorldMapPackRenderer([tile], tile_size_m=3000)
        ascii_h, legend = renderer.render_light_height_mosaic()
        self.assertIn("cell_width=2", ascii_h)
        self.assertIn("| 1 12|", ascii_h)
        self.assertIn("|-3  7|", ascii_h)
        self.assertIn("cell_width=2", legend)
        self.assertIn("z_min=-3", legend)
        self.assertIn("z_max=12", legend)

    def test_format_height_cell_width(self):
        from app.application.worldData.render.mapSymbols import (
            format_height_cell,
            height_cell_width,
            join_height_row,
        )

        self.assertEqual(height_cell_width([1, 12, -3]), 2)
        self.assertEqual(format_height_cell(1, width=2), " 1")
        self.assertEqual(format_height_cell(12, width=2), "12")
        self.assertEqual(format_height_cell(None, width=2), "  ")
        self.assertEqual(join_height_row([" 1", "12"]), " 1 12")

    def test_legend(self):
        legend = WorldMapPackRenderer.render_legend(mark_location=True)
        self.assertIn("locations_index", legend)
        self.assertNotIn("location_pin", legend)
        self.assertIn("river_bed", legend)


if __name__ == "__main__":
    unittest.main()
