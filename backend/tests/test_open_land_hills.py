"""L2 open-land hills — helper raster + plains/forest consumers.

SoT: docs/tz_world_pack_storage.md § L2 open-land hills.
"""

from __future__ import annotations

import unittest
from math import isqrt
from unittest.mock import MagicMock

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.terrain.hills.hillPlacement import place_hills
from app.application.worldData.generators.terrain.hills.hillRaster import raster_hill
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.masks.enums.maskDomainId import MaskDomainId
from app.dataModel.terrainMasks.hillPolicy import HillPolicy
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


def _square_host(x0: int, x1: int, y0: int, y1: int) -> set[tuple[int, int]]:
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


class TestHillRaster(unittest.TestCase):
    def test_rings_step_one_center_is_height(self) -> None:
        host = _square_host(0, 10, 0, 10)
        delta = raster_hill((5, 5), radius=2, height=2, host_cells=host)
        self.assertIsNotNone(delta)
        assert delta is not None
        self.assertEqual(delta[(5, 5)], 2)
        self.assertEqual(delta[(7, 5)], 1)
        self.assertNotIn((8, 5), delta)
        self.assertTrue(all(dz >= 1 for dz in delta.values()))
        for (x, y), dz in delta.items():
            dist = isqrt((x - 5) ** 2 + (y - 5) ** 2)
            self.assertLessEqual(dist, 2)
            if dist == 0:
                self.assertEqual(dz, 2)

    def test_skip_whole_hill_if_one_cell_outside_host(self) -> None:
        host = _square_host(0, 10, 0, 10)
        host.remove((6, 5))
        self.assertIsNone(
            raster_hill((5, 5), radius=2, height=2, host_cells=host),
        )

    def test_skip_at_surface_edge(self) -> None:
        host = _square_host(0, 4, 0, 4)
        self.assertIsNone(
            raster_hill((0, 0), radius=2, height=2, host_cells=host),
        )

    def test_height_one_is_flat_bump(self) -> None:
        host = _square_host(0, 6, 0, 6)
        delta = raster_hill((3, 3), radius=1, height=1, host_cells=host)
        self.assertIsNotNone(delta)
        assert delta is not None
        self.assertTrue(all(dz == 1 for dz in delta.values()))
        self.assertIn((3, 3), delta)

    def test_helper_does_not_clip(self) -> None:
        host = {(0, 0), (1, 0), (0, 1)}
        self.assertIsNone(
            raster_hill((0, 0), radius=1, height=1, host_cells=host),
        )

    def test_oval_is_narrower_on_minor_axis(self) -> None:
        from app.dataModel.terrainMasks.hillShape import HillShape

        host = _square_host(0, 20, 0, 20)
        circle = raster_hill(
            (10, 10), radius=6, height=2, host_cells=host,
            shape=HillShape.CIRCLE,
        )
        oval = raster_hill(
            (10, 10), radius=6, height=2, host_cells=host,
            shape=HillShape.OVAL, axis=0,
        )
        self.assertIsNotNone(circle)
        self.assertIsNotNone(oval)
        assert circle is not None and oval is not None
        self.assertIn((10, 16), circle)
        self.assertNotIn((10, 16), oval)
        self.assertIn((16, 10), oval)

    def test_double_circle_has_two_peaks(self) -> None:
        from app.dataModel.terrainMasks.hillShape import HillShape

        host = _square_host(0, 24, 0, 24)
        delta = raster_hill(
            (12, 12), radius=6, height=2, host_cells=host,
            shape=HillShape.DOUBLE_CIRCLE, axis=0,
        )
        self.assertIsNotNone(delta)
        assert delta is not None
        self.assertEqual(delta[(14, 12)], 2)
        self.assertEqual(delta[(10, 12)], 2)
        self.assertEqual(delta[(12, 12)], 1)


class TestPlaceHills(unittest.TestCase):
    def setUp(self) -> None:
        self.masks = WorldTerrainMasks.canonical_defaults()
        self.plains = self.masks.default_plains.system_terrain
        self.forest = self.masks.default_forests.system_terrain

    def _grid(
        self,
        n: int,
        terrain: str,
        hydro: set[tuple[int, int]] | None = None,
    ) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], str], dict]:
        z = {(x, y): 3 for x in range(n) for y in range(n)}
        t = {(x, y): terrain for x in range(n) for y in range(n)}
        hydro_map = {
            xy: MapCellHydrology(role=HydrologyCellRole.RIVER_BED)
            for xy in (hydro or ())
        }
        return z, t, hydro_map

    def test_lifts_plains_and_leaves_terrain_untouched(self) -> None:
        z, t, hydro = self._grid(16, self.plains)
        before = dict(t)
        place_hills(
            z, t, hydro,
            plains_key=self.plains,
            forest_key=self.forest,
            plains_hills=HillPolicy(min_spacing=8, radius=2, height=2),
            forest_hills=HillPolicy(min_spacing=64, radius=2, height=2),
            seed=1,
            z_min=0,
            z_max=20,
        )
        self.assertEqual(t, before)
        self.assertTrue(any(v > 3 for v in z.values()))
        self.assertLessEqual(max(z.values()), 5)

    def test_forest_does_not_paint_plains(self) -> None:
        z, t, hydro = self._grid(12, self.plains)
        place_hills(
            z, t, hydro,
            plains_key=self.plains,
            forest_key=self.forest,
            plains_hills=HillPolicy(min_spacing=64, radius=2, height=2),
            forest_hills=HillPolicy(min_spacing=6, radius=2, height=3),
            seed=2,
            z_min=0,
            z_max=20,
        )
        self.assertTrue(all(v == 3 for v in z.values()))

    def test_independent_consumers_on_split_host(self) -> None:
        z = {(x, y): 4 for x in range(20) for y in range(12)}
        t = {
            (x, y): (self.plains if x < 10 else self.forest)
            for x in range(20) for y in range(12)
        }
        policy = HillPolicy(min_spacing=6, radius=2, height=2)
        place_hills(
            z, t, {},
            plains_key=self.plains,
            forest_key=self.forest,
            plains_hills=policy,
            forest_hills=policy,
            seed=9,
            z_min=0,
            z_max=20,
        )
        plains_lift = [z[xy] for xy, key in t.items() if key == self.plains]
        forest_lift = [z[xy] for xy, key in t.items() if key == self.forest]
        self.assertTrue(any(v > 4 for v in plains_lift))
        self.assertTrue(any(v > 4 for v in forest_lift))

    def test_skip_when_l0_hydro_in_footprint(self) -> None:
        z, t, _ = self._grid(8, self.plains)
        hydro = {
            (x, y): MapCellHydrology(role=HydrologyCellRole.RIVER_BED)
            for x in range(8) for y in range(8)
        }
        place_hills(
            z, t, hydro,
            plains_key=self.plains,
            forest_key=self.forest,
            plains_hills=HillPolicy(min_spacing=4, radius=2, height=2),
            forest_hills=HillPolicy(min_spacing=64, radius=2, height=2),
            seed=1,
            z_min=0,
            z_max=20,
        )
        self.assertTrue(all(v == 3 for v in z.values()))

    def test_mountain_is_not_host(self) -> None:
        z, t, hydro = self._grid(12, "mountain")
        place_hills(
            z, t, hydro,
            plains_key=self.plains,
            forest_key=self.forest,
            plains_hills=HillPolicy(min_spacing=4, radius=2, height=2),
            forest_hills=HillPolicy(min_spacing=4, radius=2, height=2),
            seed=1,
            z_min=0,
            z_max=20,
        )
        self.assertTrue(all(v == 3 for v in z.values()))

    def test_min_spacing_between_centers(self) -> None:
        z, t, hydro = self._grid(24, self.plains)
        spacing = 10
        place_hills(
            z, t, hydro,
            plains_key=self.plains,
            forest_key=self.forest,
            plains_hills=HillPolicy(
                min_spacing=spacing, radius=2, height=2, shapes=("circle",),
            ),
            forest_hills=HillPolicy(min_spacing=64, radius=2, height=1),
            seed=3,
            z_min=0,
            z_max=20,
        )
        peaks = [(x, y) for (x, y), v in z.items() if v == 5]
        for i, (ax, ay) in enumerate(peaks):
            for bx, by in peaks[i + 1 :]:
                d2 = (ax - bx) ** 2 + (ay - by) ** 2
                self.assertGreaterEqual(d2, spacing * spacing)

    def test_z_band_does_not_cut_delta(self) -> None:
        z, t, hydro = self._grid(16, self.plains)
        place_hills(
            z, t, hydro,
            plains_key=self.plains,
            forest_key=self.forest,
            plains_hills=HillPolicy(min_spacing=8, radius=2, height=2),
            forest_hills=HillPolicy(min_spacing=64, radius=2, height=2),
            seed=1,
            z_min=0,
            z_max=20,
        )
        self.assertGreaterEqual(max(z.values()) - 3, 2)


class TestHillsInTilePrep(unittest.TestCase):
    def test_not_a_mask_domain(self) -> None:
        self.assertFalse(hasattr(MaskDomainId, "HILLS"))

    def test_build_tile_surface_state_hills_escape_z_band(self) -> None:
        cells = [
            WorldMapCellWire(tx=tx, ty=ty, surface_z=2, system_terrain="plains")
            for ty in range(2) for tx in range(2)
        ]
        parent = ParentLightTile.from_cells(
            world_uid="w-hills", gx=0, gy=0, side=2, tile_m=16, cells=cells,
        )
        w = MagicMock()
        w.world_uid = "w-hills"
        w.map_cell_size_m = 16
        w.seed = 1
        w.z_min = 0
        w.z_max = 20
        w.terrain_registry = None
        w.terrain_scalars = None
        w.terrain_masks = {
            "default_plains": {"hills": {"min_spacing": 8, "radius": 2, "height": 2}},
            "default_forests": {"hills": {"min_spacing": 64, "radius": 2, "height": 2}},
        }
        ctx = SurfaceTerrainContext(
            pole_field=MagicMock(),
            local_field=ClimateAnchorField(()),
            coarse_hm=MagicMock(),
            coarse_hydro={},
            sparse_meter_hydro={},
            meter_z_overrides={},
            coarse_relief_z={},
            coarse_surface_z={},
        )
        state = TerrainBatchOrchestrator(MagicMock()).build_tile_surface_state(
            w, [], ctx, 0, 0, parent_light=parent,
            refine_policy=ParentLightRefinePolicy(z_band=0, detail_noise_amplitude=0),
        )
        zs = list(state.heightmap.surface_z.values())
        self.assertGreaterEqual(max(zs), 4)
        self.assertTrue(all(t == "plains" for t in state.surface_terrain.values()))


if __name__ == "__main__":
    unittest.main()
