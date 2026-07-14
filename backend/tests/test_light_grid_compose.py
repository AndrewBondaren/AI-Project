"""L0 light-grid compose — tz_map_light_bake acceptance (MLB-*)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.pack.bake.lightGrid.bake import compose_light_grid
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.dataModel.worldPack.worldMapCellsPerTile import resolve_world_map_cells_per_tile
from app.db.models.namedLocation import NamedLocation


def _world(**overrides):
    base = dict(
        world_uid="world-light-test",
        map_cell_size_m=1000,
        world_map_cells_per_tile=None,
        z_min=-2,
        z_max=4,
        map_subsurface_depth=0,
        city_size_registry=[
            {"system_size": "town", "display_size": "Town", "radius": 4},
        ],
        hydrology={
            "enabled": True,
            "declared_rivers": [
                {
                    "location_uid": "river-a",
                    "declare_mode": "segments",
                    "segments": [
                        {
                            "from": {"x": 100, "y": 100, "z": 0},
                            "to": {"x": 900, "y": 100, "z": 0},
                            "connection_type": "river",
                            "width_cells": 3,
                        },
                    ],
                },
            ],
        },
        terrain_registry=[
            {"system_terrain": "plains", "display_name": "Plains"},
            {"system_terrain": "forest", "display_name": "Forest"},
        ],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestLightGridCompose(unittest.TestCase):
    def test_wp10_v2_side_constant(self):
        self.assertEqual(resolve_world_map_cells_per_tile(1000), 32)
        scale = LightGridScale.from_tile(1000, 32)
        self.assertEqual(scale.side, 32)
        self.assertEqual(scale.light_m, 31)

    def test_river_corridor_not_flat_macro_sample(self):
        world = _world()
        locations = [
            NamedLocation(
                location_uid="town-1",
                world_uid=world.world_uid,
                display_name="Town",
                system_location_type="settlement",
                system_city_size="town",
                map_x=500,
                map_y=500,
                created_at="2026-01-01T00:00:00Z",
            ),
        ]
        pole = MagicMock(spec=ClimatePoleField)
        pole.sample.return_value = SimpleNamespace(
            typical_elevation_z=1,
            system_climate_zone="temperate",
        )
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={(0, 0): 1},
        )
        surface = SurfaceTerrainContext(
            pole_field=pole,
            coarse_hm=hm,
            coarse_hydro={
                (0, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
            },
            sparse_meter_hydro={},
            meter_z_overrides={},
            coarse_surface_z={(0, 0): 1},
        )
        scale = LightGridScale.from_tile(1000, 32)
        ctx = LightGridBakeContext(
            world=world,
            locations=locations,
            locations_index=LocationsIndexWire(
                locations=[
                    LocationsIndexPin(
                        location_uid="town-1",
                        map_x=500,
                        map_y=500,
                        display_name="Town",
                        system_location_type="settlement",
                    ),
                ],
            ),
            tiles=[(0, 0)],
            scale=scale,
            surface_planning=surface,
            pole_field=pole,
            terrain_system_keys={"plains", "forest"},
        )
        compose = compose_light_grid(ctx)
        cells = compose.to_wire_tile(0, 0)
        self.assertEqual(len(cells), 1024)

        # Coarse RIVER on macro must NOT paint entire 32×32.
        river_n = sum(1 for c in cells if c.hydrology_role is WorldMapHydrologyRole.RIVER)
        none_n = sum(1 for c in cells if c.hydrology_role is WorldMapHydrologyRole.NONE)
        self.assertGreater(river_n, 0)
        self.assertLess(river_n, 1024)
        self.assertGreater(none_n, 0)

        pin_n = sum(1 for c in cells if c.location_pin is not None)
        self.assertGreater(pin_n, 1)

        z_values = {c.surface_z for c in cells}
        self.assertGreaterEqual(len(z_values), 1)


if __name__ == "__main__":
    unittest.main()
