"""Unit tests for bootstrap macro tile selection."""

import unittest
from types import SimpleNamespace

from app.application.worldData.generators.terrain.passes.bootstrapMacroTiles import (
    bootstrap_macro_tiles,
)
from app.db.models.namedLocation import NamedLocation


def _world(**kwargs):
    defaults = {
        "world_uid": "test-world",
        "hydrology": {"enabled": True},
        "map_cell_size_m": 3000,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**kwargs)


def _loc(uid: str, x: int, y: int, z: int = 0) -> NamedLocation:
    return NamedLocation(
        world_uid="test-world",
        location_uid=uid,
        display_name=uid,
        map_x=x,
        map_y=y,
        map_z=z,
        is_mobile=False,
    )


class TestBootstrapMacroTiles(unittest.TestCase):

    def test_anchor_tile_has_highest_priority(self):
        world = _world()
        loc = _loc("pole-north", 15000, 9000, 10)
        tiles = bootstrap_macro_tiles(world, [loc], {}, {}, max_tiles=1)
        self.assertEqual(tiles, [(5, 3)])

    def test_max_tiles_caps_output(self):
        world = _world()
        locs = [
            _loc("a", 0, 0),
            _loc("b", 3000, 0),
            _loc("c", 6000, 0),
        ]
        coarse = {(9, 9): object(), (10, 10): object()}
        tiles = bootstrap_macro_tiles(world, locs, coarse, {}, max_tiles=2)
        self.assertEqual(len(tiles), 2)
        self.assertIn((0, 0), tiles)

    def test_meter_hydro_adds_tile(self):
        world = _world(hydrology={"enabled": False})
        sparse = {(7500, 4500): object()}
        tiles = bootstrap_macro_tiles(world, [], {}, sparse, max_tiles=None)
        self.assertIn((2, 1), tiles)


if __name__ == "__main__":
    unittest.main()
