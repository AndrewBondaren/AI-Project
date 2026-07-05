"""Unit tests — wire `world.hydrology.declared_*` → loadDeclaredHydrology."""

import unittest
from types import SimpleNamespace

from app.application.jsonValidation.facade import normalize_world
from app.application.worldData.generators.terrain.hydrology.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.db.models.namedLocation import NamedLocation


def _world(**kwargs):
    defaults = {
        "world_uid": "test-world",
        "map_cell_size_m": 3000,
        "hydrology": {"enabled": True},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestDeclaredWire(unittest.TestCase):

    def test_normalize_and_load_coastline(self):
        raw = {
            "world_uid": "test-world",
            "map_cell_size_m": 3000,
            "hydrology": {
                "declared_coastlines": [{
                    "location_uid": "loc-sea",
                    "path": [
                        {"x": 6000, "y": 6000, "z": 0},
                        {"x": 24000, "y": 6000, "z": 0},
                    ],
                }],
            },
        }
        normalized = normalize_world(raw)
        w = SimpleNamespace(**normalized)
        loaded = load_declared_hydrology(w, [])
        self.assertEqual(len(loaded.coastline_segments), 1)
        self.assertEqual(loaded.coastline_segments[0], ((2, 2), (8, 2)))

    def test_load_lake_and_river_segments(self):
        w = _world(hydrology={
            "declared_lakes": [{
                "location_uid": "loc-lake",
                "shoreline": [
                    {"x": 3000, "y": 3000, "z": 0},
                    {"x": 6000, "y": 3000, "z": 0},
                    {"x": 4500, "y": 4500, "z": 0},
                ],
            }],
            "declared_rivers": [{
                "location_uid": "loc-river",
                "system_role": "stem",
                "declare_mode": "segments",
                "segments": [{
                    "from": {"x": 3000, "y": 9000, "z": 0},
                    "to": {"x": 6000, "y": 9000, "z": 0},
                    "connection_type": "river",
                    "width_cells": 2,
                }],
            }],
        })
        loc = NamedLocation(
            location_uid="loc-lake",
            world_uid="test-world",
            display_name="Lake",
            system_location_type="geographic",
            system_location_subtype="lake",
            created_at="2026-06-26T00:00:00",
        )
        loaded = load_declared_hydrology(w, [loc])
        self.assertEqual(len(loaded.lake_specs), 1)
        self.assertEqual(loaded.lake_specs[0].location_uid, "loc-lake")
        self.assertEqual(len(loaded.river_edges), 1)
        self.assertEqual(loaded.river_edges[0].segment, ((1, 3), (2, 3)))
        self.assertEqual(len(loaded.river_intents), 0)

    def test_endpoints_deferred_to_generate(self):
        w = _world(hydrology={
            "declared_rivers": [{
                "location_uid": "loc-river",
                "system_role": "stem",
                "declare_mode": "endpoints",
                "source": {"x": 3000, "y": 9000, "z": 0},
                "mouth": {"location_uid": "loc-sea"},
            }],
        })
        loaded = load_declared_hydrology(w, [])
        self.assertEqual(len(loaded.river_edges), 0)
        self.assertEqual(len(loaded.river_intents), 1)
        self.assertEqual(loaded.river_intents[0].declare_mode, RiverDeclareMode.ENDPOINTS)


if __name__ == "__main__":
    unittest.main()
