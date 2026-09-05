"""SQL overlay on pack location pins — tz_pack_ascii_render L0 identity."""

from __future__ import annotations

import unittest

from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.lightMapCells import wire_symbol
from app.application.worldData.render.locationPinOverlay import (
    l0_settlement_glyph,
    overlay_location_pins,
)
from app.application.worldData.render.worldMapPackRenderer import WorldMapPackRenderer
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.db.models.namedLocation import NamedLocation


def _loc(
    uid: str,
    *,
    loc_type: str = "settlement",
    subtype: str | None = "village",
    size: str | None = "village",
    name: str = "Place",
) -> NamedLocation:
    return NamedLocation(
        location_uid=uid,
        world_uid="w",
        display_name=name,
        system_location_type=loc_type,
        created_at="2026-01-01T00:00:00Z",
        system_location_subtype=subtype,
        system_city_size=size,
    )


class TestLocationPinOverlay(unittest.TestCase):
    def test_preserves_order_and_copies_sql_fields(self) -> None:
        index = LocationsIndexWire(
            locations=[
                LocationsIndexPin(
                    location_uid="a", map_x=1, map_y=2, system_location_type="settlement",
                ),
                LocationsIndexPin(
                    location_uid="b", map_x=3, map_y=4, system_location_type="geographic",
                ),
            ],
        )
        overlaid = overlay_location_pins(
            index,
            [_loc("b", loc_type="geographic", subtype="peak", size=None, name="Peak"),
             _loc("a", subtype="village", name="Ham")],
        )
        self.assertEqual([p.location_uid for p in overlaid.locations], ["a", "b"])
        self.assertEqual(overlaid.locations[0].map_x, 1)
        self.assertEqual(overlaid.locations[0].system_location_subtype, "village")
        self.assertEqual(overlaid.locations[0].display_name, "Ham")
        self.assertEqual(overlaid.locations[1].system_location_subtype, "peak")
        self.assertEqual(overlaid.locations[1].system_location_type, "geographic")

    def test_missing_sql_row_keeps_pack_pin(self) -> None:
        pin = LocationsIndexPin(
            location_uid="ghost", map_x=0, map_y=0, system_location_type="settlement",
        )
        overlaid = overlay_location_pins(
            LocationsIndexWire(locations=[pin]),
            [_loc("other")],
        )
        self.assertEqual(overlaid.locations[0].location_uid, "ghost")
        self.assertIsNone(overlaid.locations[0].system_location_subtype)

    def test_sql_village_glyph_without_pack_subtype(self) -> None:
        index = LocationsIndexWire(
            locations=[
                LocationsIndexPin(
                    location_uid="v1", map_x=0, map_y=0, system_location_type="settlement",
                ),
            ],
        )
        overlaid = overlay_location_pins(index, [_loc("v1")])
        cell = WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains", location_pin=0)
        self.assertEqual(wire_symbol(cell, pins=overlaid.locations), "n")
        self.assertEqual(l0_settlement_glyph(overlaid.locations[0]), "n")

    def test_render_grid_uses_overlaid_village(self) -> None:
        cells = {
            (0, 0): WorldMapCellWire(
                tx=0, ty=0, surface_z=1, system_terrain="plains", location_pin=0,
            ),
        }
        tile = PackTileLightView(gx=0, gy=0, side=1, cells=cells)
        pack_pins = LocationsIndexWire(
            locations=[
                LocationsIndexPin(
                    location_uid="v1", map_x=0, map_y=0, system_location_type="settlement",
                ),
            ],
        )
        pins = overlay_location_pins(pack_pins, [_loc("v1")])
        light = WorldMapPackRenderer(
            [tile], tile_size_m=3000, pins=pins,
        ).render_tile_light_grid(0, 0, mark_location=True)
        self.assertIn("n", light)
        self.assertNotIn("@", light)


if __name__ == "__main__":
    unittest.main()
