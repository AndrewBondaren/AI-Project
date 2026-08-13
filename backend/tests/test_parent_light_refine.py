"""WP-PERF-22 — parent light cache, upsample z-band, hard hydro corridor."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.application.worldData.generators.hydrology.shore.parentLightHydroCorridor import (
    hydro_mask_from_parent,
    merge_hydro_hard_corridor,
)
from app.application.worldData.generators.terrain.passes.parentLightTerrain import (
    upsample_terrain_from_parent_light,
)
from app.application.worldData.generators.terrain.passes.parentLightUpsample import (
    upsample_from_parent_light,
)
from app.application.worldData.generators.terrain.passes.columnFillPass import run_column_fill
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.types import ColumnRect, SurfaceHeightmap
from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.read.parentLightLoad import load_parent_light
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


def _parent_mixed_terrain(*, side: int = 2, tile_m: int = 8) -> ParentLightTile:
    """Left light cells mountain, right plains."""
    cells = [
        WorldMapCellWire(tx=0, ty=0, surface_z=5, system_terrain="mountain"),
        WorldMapCellWire(tx=1, ty=0, surface_z=2, system_terrain="plains"),
        WorldMapCellWire(tx=0, ty=1, surface_z=5, system_terrain="mountain"),
        WorldMapCellWire(tx=1, ty=1, surface_z=2, system_terrain="plains"),
    ]
    return ParentLightTile.from_cells(
        world_uid="w-mask",
        gx=0,
        gy=0,
        side=side,
        tile_m=tile_m,
        cells=cells,
    )


def _parent_with_river(*, side: int = 4, tile_m: int = 32) -> ParentLightTile:
    cells: list[WorldMapCellWire] = []
    for ty in range(side):
        for tx in range(side):
            role = WorldMapHydrologyRole.RIVER if ty == side // 2 else WorldMapHydrologyRole.NONE
            cells.append(
                WorldMapCellWire(
                    tx=tx,
                    ty=ty,
                    surface_z=2 if role is WorldMapHydrologyRole.NONE else 1,
                    system_terrain="plains",
                    hydrology_role=role,
                    hydrology_width=2 if role is WorldMapHydrologyRole.RIVER else None,
                ),
            )
    return ParentLightTile.from_cells(
        world_uid="w-parent",
        gx=0,
        gy=0,
        side=side,
        tile_m=tile_m,
        cells=cells,
    )


class TestParentLightCache(unittest.TestCase):
    def test_write_through_then_load_hits_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            uid = "w-cache"
            paths = WorldPackPaths.from_db_parent(str(Path(tmp) / "game.db"), uid)
            writer = WorldPackWriter(paths)
            writer.sync_world_metadata(
                SimpleNamespace(map_cell_size_m=32, world_map_cells_per_tile=None),
                cells_per_side=2,
            )
            cells = [
                WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains"),
                WorldMapCellWire(tx=1, ty=0, surface_z=2, system_terrain="plains"),
                WorldMapCellWire(tx=0, ty=1, surface_z=1, system_terrain="plains"),
                WorldMapCellWire(tx=1, ty=1, surface_z=2, system_terrain="plains"),
            ]
            writer.write_world_map_tile(0, 0, cells, cells_per_side=2)
            writer.save_manifest()

            cached = writer.parent_light_cache.get(uid, 0, 0)
            self.assertIsNotNone(cached)
            assert cached is not None
            self.assertEqual(cached.surface_z_at(1, 0), 2)

            # Clear cache → disk load → put again
            writer.parent_light_cache.clear()
            reader = WorldPackReader(paths)
            loaded = load_parent_light(
                uid, 0, 0, reader=reader, cache=writer.parent_light_cache, tile_m=32,
            )
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.surface_z_at(1, 0), 2)
            self.assertIsNotNone(writer.parent_light_cache.get(uid, 0, 0))


class TestUpsampleAndCorridor(unittest.TestCase):
    def test_z_band_respected(self) -> None:
        parent = _parent_with_river(side=4, tile_m=16)
        policy = ParentLightRefinePolicy(z_band=1, detail_noise_amplitude=1)
        w = MagicMock()
        w.world_uid = "w-parent"
        w.map_cell_size_m = 16
        w.seed = 7
        # terrain_scalars path — provide z bounds via world attributes if used
        w.z_min = -5
        w.z_max = 10
        w.terrain_scalars = None

        fine = upsample_from_parent_light(parent, w, policy=policy)
        self.assertEqual(len(fine), 16 * 16)
        l0_zs = [c.surface_z for c in parent.cells.values()]
        lo = min(l0_zs) - policy.z_band
        hi = max(l0_zs) + policy.z_band
        for z in fine.values():
            self.assertGreaterEqual(z, lo)
            self.assertLessEqual(z, hi)

    def test_hard_corridor_keeps_river_only_in_mask(self) -> None:
        parent = _parent_with_river(side=4, tile_m=16)
        mask = hydro_mask_from_parent(parent)
        self.assertTrue(mask)
        for (_xm, _ym), entry in mask.items():
            self.assertEqual(entry.role, HydrologyCellRole.RIVER_BED)

        outside = (0, 0)
        sparse = {
            outside: MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
        }
        merged = merge_hydro_hard_corridor(parent, sparse)
        if outside not in mask:
            self.assertNotIn(outside, merged)

    def test_build_tile_surface_state_requires_parent(self) -> None:
        terrain = TerrainBatchOrchestrator(MagicMock())
        with self.assertRaises(TypeError):
            terrain.build_tile_surface_state(
                MagicMock(), [], MagicMock(), 0, 0,
            )

        parent = _parent_with_river(side=2, tile_m=8)
        w = MagicMock()
        w.world_uid = "w-parent"
        w.map_cell_size_m = 8
        w.seed = 1
        w.z_min = -2
        w.z_max = 8
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
        state = terrain.build_tile_surface_state(
            w, [], ctx, 0, 0, parent_light=parent,
        )
        self.assertTrue(state.heightmap.surface_z)
        self.assertTrue(state.hydrology)
        self.assertIsNotNone(state.surface_terrain)
        assert state.surface_terrain is not None
        self.assertTrue(state.surface_terrain)
        self.assertTrue(all(t == "plains" for t in state.surface_terrain.values()))

    def test_surface_z_at_miss_raises(self) -> None:
        parent = ParentLightTile.from_cells(
            world_uid="w",
            gx=0,
            gy=0,
            side=2,
            tile_m=8,
            cells=[],
        )
        with self.assertRaises(LookupError):
            parent.surface_z_at(0, 0)


class TestTerrainMaskCarry(unittest.TestCase):
    def test_upsample_terrain_nearest_preserves_l0_mask(self) -> None:
        parent = _parent_mixed_terrain(side=2, tile_m=8)
        w = MagicMock()
        w.world_uid = "w-mask"
        w.terrain_registry = None
        fine = upsample_terrain_from_parent_light(parent, w)
        self.assertEqual(len(fine), 8 * 8)
        # World meters for tile (0,0): lx in left half → mountain
        left = {(xm, ym) for (xm, ym), t in fine.items() if t == "mountain"}
        right = {(xm, ym) for (xm, ym), t in fine.items() if t == "plains"}
        self.assertTrue(left)
        self.assertTrue(right)
        self.assertEqual(len(left) + len(right), 64)
        for xm, _ym in left:
            self.assertLess(xm % 8, 4)  # tile-local lx via xm since gx=0
        for xm, _ym in right:
            self.assertGreaterEqual(xm % 8, 4)

    def test_column_fill_uses_surface_terrain_not_default_forest(self) -> None:
        parent = _parent_mixed_terrain(side=2, tile_m=4)
        w = MagicMock()
        w.world_uid = "w-mask"
        w.terrain_registry = None
        w.terrain_masks = None
        w.terrain_scalars = None
        w.closed_planet_grid = False
        w.magma_band_thickness = None
        w.z_min = -2
        w.z_max = 20
        w.map_subsurface_depth = 0
        fine_z = upsample_from_parent_light(
            parent, w, policy=ParentLightRefinePolicy(detail_noise_amplitude=0),
        )
        fine_t = upsample_terrain_from_parent_light(parent, w)
        bbox = GridBBox(x_min=0, x_max=3, y_min=0, y_max=3)
        heightmap = SurfaceHeightmap(
            world_uid="w-mask",
            bbox=bbox,
            surface_z={(x, y): fine_z[(x, y)] for x in range(4) for y in range(4)},
        )
        n_eff = {(x, y): 0 for x in range(4) for y in range(4)}
        cells = run_column_fill(
            w,
            heightmap,
            n_eff,
            surface_terrain=fine_t,
        )
        surface = [c for c in cells if c.z == heightmap.surface_z[(c.x, c.y)]]
        terrains = {c.system_terrain for c in surface}
        self.assertIn("mountain", terrains)
        self.assertIn("plains", terrains)
        self.assertNotIn("forest", terrains)

    def test_build_tile_surface_state_carries_mixed_mask(self) -> None:
        terrain = TerrainBatchOrchestrator(MagicMock())
        parent = _parent_mixed_terrain(side=2, tile_m=8)
        w = MagicMock()
        w.world_uid = "w-mask"
        w.map_cell_size_m = 8
        w.seed = 1
        w.z_min = -2
        w.z_max = 20
        w.terrain_registry = None
        w.terrain_scalars = None
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
        state = terrain.build_tile_surface_state(
            w, [], ctx, 0, 0, parent_light=parent,
        )
        assert state.surface_terrain is not None
        self.assertIn("mountain", set(state.surface_terrain.values()))
        self.assertIn("plains", set(state.surface_terrain.values()))

        parent = ParentLightTile.from_cells(
            world_uid="w",
            gx=0,
            gy=0,
            side=2,
            tile_m=8,
            cells=[],
        )
        with self.assertRaises(LookupError):
            parent.surface_z_at(0, 0)


class TestRefineFailClosed(unittest.IsolatedAsyncioTestCase):
    async def test_refine_rects_missing_parent_raises(self) -> None:
        from app.application.worldData.pack.refine.fineTerrainRefineOrchestrator import (
            FineTerrainRefineOrchestrator,
        )
        from app.application.worldData.pack.read.parentLightLoad import MissingParentLightError
        from app.application.worldData.materializationContext import MaterializationContext

        terrain = MagicMock()
        writer = MagicMock()
        writer.paths = MagicMock()
        writer.parent_light_cache = MagicMock()
        l2 = FineTerrainRefineOrchestrator(terrain)
        world = SimpleNamespace(
            world_uid="w-miss",
            map_cell_size_m=32,
            terrain_chunk_columns=16,
            terrain_parallel_workers=None,
        )
        with patch(
            "app.application.worldData.pack.refine.fineChunkRunner.require_parent_light",
            side_effect=MissingParentLightError("w-miss", 0, 0),
        ):
            with self.assertRaises(MissingParentLightError):
                await l2._refine_rects(
                    world,
                    [],
                    writer,
                    MaterializationContext(free_cores=1),
                    surface_ctx=MagicMock(),
                    tile_gx=0,
                    tile_gy=0,
                    rects=[ColumnRect(x_min=0, x_max=1, y_min=0, y_max=1)],
                    volumes=[],
                    refine_role="scene",
                    phase="scene",
                )


if __name__ == "__main__":
    unittest.main()
