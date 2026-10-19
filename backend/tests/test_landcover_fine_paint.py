"""Wilderness-7 — L2 region paint in build_tile_surface_state.

Fine edge must be crisp in fine coordinates, not the L0 stair; columns carry
``region_uid``; background is restored outside the precise contour; hydro is
older than landcover.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.materialize.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.application.worldData.pack.read.mapCellToFineTerrainWire import (
    cells_to_fine_terrain_chunk,
)
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.spatial.regionShape import BboxShape, EdgeNoise
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.worldTerrainScalars import WorldTerrainScalars
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.dataModel.terrainMasks.regions import ForestSpec
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.wire.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.wire.parentLightTile import ParentLightTile
from app.dataModel.worldPack.wire.worldMapCellWire import WorldMapCellWire
from app.db.models.mapCell import MapCell
from app.ids.regionIdentity import region_uid

FOREST = WorldTerrainRegistry.forest_terrain_key()
PLAINS = WorldTerrainRegistry.plains_terrain_key()
TILE_M = 8
SIDE = 2  # light_span = 4


def _world(*specs) -> SimpleNamespace:
    registry = WorldTerrainRegistry.canonical_defaults()
    masks = WorldTerrainMasks(
        default_landcover=LandcoverRegionsCategoryPolicy(
            autoresolve=False, seed_spacing=8, max_radius=10,
            claim_noise=EdgeNoise(amplitude=3, scale=4),
        ),
        declared_regions=list(specs),
    )
    world = SimpleNamespace(
        world_uid="wilderness-7", seed=7,
        world_topology_mode="planar",
        world_bounds={"x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0},
        terrain_registry=registry.model_dump(mode="json"),
        terrain_masks=masks.model_dump(mode="json"),
        hydrology={"enabled": False},
        climate_zone_registry=[
            ClimateZone.ARID.to_entry().model_dump(mode="json"),
            ClimateZone.TEMPERATE.to_entry().model_dump(mode="json"),
        ],
        z_min=-2, z_max=20,
    )
    return world


def _surface_ctx() -> SurfaceTerrainContext:
    return SurfaceTerrainContext(
        pole_field=MagicMock(),
        local_field=ClimateAnchorField(()),
        coarse_hm=MagicMock(),
        coarse_hydro={},
        sparse_fine_hydro={},
        fine_z_overrides={},
        coarse_relief_z={},
        coarse_surface_z={},
    )


def _parent() -> ParentLightTile:
    """Hand-shaped L0 state: (0,0) river, (1,0) background, (0,1)+(1,1) region."""
    uid = region_uid("wilderness-7", name="woods")
    zone = ClimateZone.ARID.world_map_wire_id()  # rainfall 10 → plains background
    cells = [
        WorldMapCellWire(tx=0, ty=0, surface_z=2, system_terrain=PLAINS,
                         hydrology_role=WorldMapHydrologyRole.RIVER,
                         climate_zone_id=zone),
        WorldMapCellWire(tx=1, ty=0, surface_z=2, system_terrain=PLAINS,
                         climate_zone_id=zone),
        WorldMapCellWire(tx=0, ty=1, surface_z=2, system_terrain=FOREST,
                         region_uid=uid, climate_zone_id=zone),
        WorldMapCellWire(tx=1, ty=1, surface_z=2, system_terrain=FOREST,
                         region_uid=uid, climate_zone_id=zone),
    ]
    return ParentLightTile.from_cells(
        world_uid="wilderness-7", gx=0, gy=0, side=SIDE, tile_macro=TILE_M,
        cells=cells,
    )


class FineRegionPaintTests(unittest.TestCase):
    """Region bbox x 0..5, y 0..6 on an 8×8 tile: edge cuts light cells."""

    def setUp(self):
        self.spec = ForestSpec(name="woods", shape=BboxShape(x_min=0, y_min=0, x_max=5, y_max=6))
        self.world = _world(self.spec)
        self.uid = region_uid(self.world.world_uid, name="woods")
        self.state = TerrainBatchOrchestrator(MagicMock()).build_tile_surface_state(
            self.world, [], _surface_ctx(), 0, 0, parent_light=_parent(),
        )

    def test_fine_edge_cuts_inside_light_cell(self) -> None:
        terrain = self.state.surface_terrain
        assert terrain is not None
        uid = self.state.surface_region_uid
        assert uid is not None
        for x in (4, 5):  # inside region, parent light cell was background
            for y in (0, 1, 2):
                self.assertEqual(terrain[(x, y)], FOREST, (x, y))
                self.assertEqual(uid.get((x, y)), self.uid)
        for x in (6, 7):  # outside region, parent was background → stays
            self.assertEqual(terrain[(x, 0)], PLAINS)
            self.assertNotIn((x, 0), uid)

    def test_background_restored_outside_precise_contour(self) -> None:
        terrain = self.state.surface_terrain
        assert terrain is not None
        # Cell (0,1) was region-painted at L0 but y=7 is outside the contour.
        self.assertEqual(terrain[(0, 6)], FOREST)
        self.assertEqual(self.state.surface_region_uid[(0, 6)], self.uid)
        self.assertEqual(terrain[(0, 7)], PLAINS)
        self.assertNotIn((0, 7), self.state.surface_region_uid)

    def test_hydro_preserved_under_region(self) -> None:
        terrain = self.state.surface_terrain
        assert terrain is not None
        for x in range(4):  # cell (0,0): RIVER → forest paint must not land
            for y in range(4):
                self.assertEqual(terrain[(x, y)], PLAINS)
                self.assertNotIn((x, y), self.state.surface_region_uid)

    def test_column_region_uid_on_wire(self) -> None:
        chunk = cells_to_fine_terrain_chunk(
            0, 0, 4, 0, 0,
            [MapCell(world_uid="w", x=4, y=2, z=2, system_terrain=FOREST)],
            region_uid_by_xy={(4, 2): self.uid},
        )
        self.assertEqual(chunk.columns[0].region_uid, self.uid)
        chunk = cells_to_fine_terrain_chunk(
            0, 0, 4, 0, 0,
            [MapCell(world_uid="w", x=6, y=0, z=2, system_terrain=PLAINS)],
            region_uid_by_xy={(4, 2): self.uid},
        )
        self.assertIsNone(chunk.columns[0].region_uid)

    def test_no_regions_no_paint(self) -> None:
        world = _world()
        world.terrain_masks = WorldTerrainMasks(default_landcover=LandcoverRegionsCategoryPolicy.canonical_defaults().model_copy(
            update={"enabled": False})).model_dump(mode="json")
        state = TerrainBatchOrchestrator(MagicMock()).build_tile_surface_state(
            world, [], _surface_ctx(), 0, 0, parent_light=_parent(),
        )
        assert state.surface_terrain is not None
        self.assertEqual(state.surface_terrain[(0, 6)], FOREST)  # pure upsample
        self.assertIsNone(state.surface_region_uid)

    def test_declared_without_explicit_policy_uses_canonical(self) -> None:
        world = _world(self.spec)
        world.terrain_masks = WorldTerrainMasks(
            declared_regions=[self.spec],
        ).model_dump(mode="json")
        state = TerrainBatchOrchestrator(MagicMock()).build_tile_surface_state(
            world, [], _surface_ctx(), 0, 0, parent_light=_parent())
        self.assertIn(self.uid, state.surface_region_uid.values())


if __name__ == "__main__":
    unittest.main()
