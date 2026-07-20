"""Cleanup acceptance — footprint POJO, hydro SEA/RIVER, climate wire, mosaic SoT."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.coarseOpenWater import (
    apply_coarse_open_water,
)
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.raster import paint_role
from app.application.worldData.pack.bake.lightGrid.contributors.settlement import (
    SettlementContributor,
)
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.read.packReadServices import build_pack_read_services
from app.application.worldData.patchStoreService import PatchStoreService
from app.application.worldData.render.mapGridRenderService import MapGridRenderService
from app.application.worldData.render.packMapGridRender import PackMapGridRender
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.worldPack import WorldMapCellWire
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.lightSettlementFootprint import LightSettlementFootprintPolicy
from app.dataModel.worldPack.worldMapCellsPerTile import (
    resolve_world_map_cells_per_tile,
    resolve_world_map_side,
)
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire


class TestLightBakeCleanup(unittest.TestCase):
    def test_footprint_policy_is_sot(self) -> None:
        pol = LightSettlementFootprintPolicy.canonical_defaults()
        self.assertEqual(pol.scale_divisor, 8.0)
        self.assertEqual(pol.radius_light(None, 32), 4)  # ceil(sqrt(1)*32/8)
        self.assertEqual(pol.radius_light(0, 32), 4)
        self.assertGreaterEqual(pol.radius_light(64, 32), pol.min_radius_light)
        src = inspect.getsource(SettlementContributor.apply)
        self.assertNotIn("8.0", src)
        self.assertNotIn("/ 8", src)

    def test_wp10_side_ignores_tile_m(self) -> None:
        self.assertEqual(resolve_world_map_cells_per_tile(1000), 32)
        self.assertEqual(resolve_world_map_cells_per_tile(3000), 32)
        self.assertEqual(resolve_world_map_side(), 32)
        self.assertEqual(resolve_world_map_side(16), 16)

    def test_climate_zone_wire_id_stable(self) -> None:
        self.assertEqual(ClimateZone.TEMPERATE.world_map_wire_id(), 6)
        self.assertEqual(ClimateZone.ARCTIC.world_map_wire_id(), 0)
        self.assertEqual(ClimateZone.WARM.world_map_wire_id(), 16)
        again = ClimateZone.from_world_map_wire_id(6)
        self.assertIs(again, ClimateZone.TEMPERATE)
        # Contributor must use wire_id API, not enumerate
        from app.application.worldData.pack.bake.lightGrid.contributors import climate as climate_mod

        src = inspect.getsource(climate_mod)
        self.assertNotIn("enumerate(", src)
        self.assertIn("world_map_wire_id", src)

    def test_coarse_sea_skips_existing_river(self) -> None:
        scale = LightGridScale.from_tile(1000, 4)
        compose = LightGridCompose(scale)
        tile_set = {(0, 0)}
        # Declared river through center of macro tile
        river_cells = {(1, 1), (2, 1)}
        paint_role(
            compose,
            river_cells,
            WorldMapHydrologyRole.RIVER,
            width=1,
            tile_set=tile_set,
        )
        pole = MagicMock(spec=ClimatePoleField)
        hm = SurfaceHeightmap(
            world_uid="w",
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={(0, 0): 0},
        )
        surface = SurfaceTerrainContext(
            pole_field=pole,
            local_field=ClimateAnchorField(()),
            coarse_hm=hm,
            coarse_hydro={
                (0, 0): MapCellHydrology(role=HydrologyCellRole.COASTAL_SEA),
            },
            sparse_meter_hydro={},
            meter_z_overrides={},
            coarse_relief_z={(0, 0): 0},
            coarse_surface_z={(0, 0): 0},
        )
        ctx = LightGridBakeContext(
            world=SimpleNamespace(world_uid="w"),
            locations=[],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=[(0, 0)],
            scale=scale,
            surface_planning=surface,
        )
        apply_coarse_open_water(compose, ctx)
        self.assertEqual(
            compose.ensure(0, 0, 1, 1).hydrology_role,
            WorldMapHydrologyRole.RIVER,
        )
        self.assertEqual(
            compose.ensure(0, 0, 0, 0).hydrology_role,
            WorldMapHydrologyRole.SEA,
        )


class TestWorldGridMosaic(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmpdir.name) / "game.db")
        self.uid = "w-mosaic-sot"
        paths = WorldPackPaths.from_db_parent(self.db_path, self.uid)
        writer = WorldPackWriter(paths)
        # Many tiles — formerly triggered MACRO AGGREGATE; must stay mask mosaic.
        for gx in range(5):
            for gy in range(4):
                writer.write_world_map_tile(
                    gx,
                    gy,
                    [WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains")],
                    cells_per_side=2,
                )
        writer.save_manifest()
        self.pack = build_pack_read_services(
            self.uid, PatchStoreService(), db_path=self.db_path,
        )
        self.world = SimpleNamespace(
            world_uid=self.uid,
            map_cell_size_m=3000,
            world_bounds=None,
            grid_bbox_padding=2,
        )
        self.map_cells = MagicMock()
        self.map_cells.uses_pack_read.return_value = True
        self.map_cells.pack_read_services.return_value = self.pack
        self.map_cells.get_all_for_read = AsyncMock(return_value=[])
        self.svc = MapGridRenderService(self.map_cells)

    async def asyncTearDown(self) -> None:
        self._tmpdir.cleanup()

    async def test_world_grid_always_light_mask_mosaic(self) -> None:
        payload = await self.svc.render_world_grid(self.world)
        self.assertEqual(payload["read_path"], "pack")
        self.assertEqual(payload["read_mode"], "world_map_light_mask")
        self.assertIn("pack L0 light mosaic", payload["ascii"])
        self.assertNotIn("MACRO AGGREGATE", payload["ascii"])

    async def test_world_grid_mosaic_when_bbox(self) -> None:
        payload = await self.svc.render_world_grid(
            self.world, gx0=0, gy0=0, gx1=1, gy1=1,
        )
        self.assertEqual(payload["read_mode"], "world_map_light_mask")
        self.assertIn("macro Gx0..Gx1 Gy0..Gy1", payload["ascii"])

    async def test_mlb12_frame_from_declared_world_bounds(self) -> None:
        """Sparse bake: frame = world_bounds; missing tiles = spaces."""
        sparse_uid = "w-mlb12-bounds"
        paths = WorldPackPaths.from_db_parent(self.db_path, sparse_uid)
        writer = WorldPackWriter(paths)
        writer.write_world_map_tile(
            0, 0,
            [
                WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains"),
                WorldMapCellWire(tx=1, ty=0, surface_z=1, system_terrain="plains"),
                WorldMapCellWire(tx=0, ty=1, surface_z=1, system_terrain="plains"),
                WorldMapCellWire(tx=1, ty=1, surface_z=1, system_terrain="mountain"),
            ],
            cells_per_side=2,
        )
        writer.save_manifest()
        pack = build_pack_read_services(
            sparse_uid, PatchStoreService(), db_path=self.db_path,
        )
        world = SimpleNamespace(
            world_uid=sparse_uid,
            map_cell_size_m=3000,
            world_bounds={"x_min": -1, "x_max": 1, "y_min": -1, "y_max": 1},
            grid_bbox_padding=2,
        )
        render = PackMapGridRender(pack.render)
        payload = render.render_world_grid(world).to_dict()
        self.assertEqual(payload["read_mode"], "world_map_light_mask")
        self.assertIn("macro Gx-1..Gx1 Gy-1..Gy1", payload["ascii"])
        self.assertNotIn("MACRO AGGREGATE", payload["ascii"])

    async def test_mlb12_frame_from_pins_when_no_bounds(self) -> None:
        sparse_uid = "w-mlb12-pins"
        paths = WorldPackPaths.from_db_parent(self.db_path, sparse_uid)
        writer = WorldPackWriter(paths)
        writer.write_world_map_tile(
            0, 0,
            [WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains")],
            cells_per_side=2,
        )
        writer.write_locations_index(
            LocationsIndexWire(
                locations=[
                    LocationsIndexPin(
                        location_uid="loc-a",
                        map_x=1500,
                        map_y=1500,
                        display_name="A",
                    ),
                ],
            ),
        )
        writer.save_manifest()
        pack = build_pack_read_services(
            sparse_uid, PatchStoreService(), db_path=self.db_path,
        )
        world = SimpleNamespace(
            world_uid=sparse_uid,
            map_cell_size_m=3000,
            world_bounds=None,
            grid_bbox_padding=2,
        )
        render = PackMapGridRender(pack.render)
        payload = render.render_world_grid(world).to_dict()
        # pin at tile (0,0) + padding 2 → Gx-2..Gx2 Gy-2..Gy2
        self.assertIn("macro Gx-2..Gx2 Gy-2..Gy2", payload["ascii"])


if __name__ == "__main__":
    unittest.main()
