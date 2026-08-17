"""U15 category shore paint — not world-level default_shore."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.shore.shoreProfile import (
    infer_shore_kind,
    shore_terrain_material,
)
from app.application.worldData.generators.terrain.passes.columnFillPass import run_column_fill
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain


def _world(**kwargs):
    defaults = {
        "world_uid": "w-shore-paint",
        "hydrology": WorldHydrology().model_dump(mode="json"),
        "terrain_registry": None,
        "terrain_masks": None,
        "terrain_scalars": None,
        "closed_planet_grid": False,
        "magma_band_thickness": None,
        "z_min": 0,
        "z_max": 20,
        "map_subsurface_depth": 0,
        "map_cell_size_m": 3000,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class ShoreCategoryPaintTest(unittest.TestCase):

    def test_defaults_follow_category_pojo(self) -> None:
        world = _world()
        river_t, river_m = shore_terrain_material(world, HydrologyShoreKind.RIVER)
        lake_t, _ = shore_terrain_material(world, HydrologyShoreKind.LAKE)
        sea_t, _ = shore_terrain_material(world, HydrologyShoreKind.SEA)
        mtn_t, mtn_m = shore_terrain_material(world, HydrologyShoreKind.MOUNTAIN_RIVER)
        self.assertEqual(river_t, ReliefConditionTerrain.SHORE_RIVER.value)
        self.assertEqual(lake_t, ReliefConditionTerrain.SHORE_LAKE.value)
        self.assertEqual(sea_t, ReliefConditionTerrain.SHORE_SEA.value)
        self.assertEqual(mtn_t, ReliefConditionTerrain.SHORE_MOUNTAIN_RIVER.value)
        self.assertEqual(river_m, "sand")
        self.assertEqual(mtn_m, "stone")

    def test_does_not_read_legacy_default_shore(self) -> None:
        hydro = WorldHydrology().model_dump(mode="json")
        hydro["default_shore"] = {
            "system_terrain": "shore",
            "system_material": "sand",
        }
        world = _world(hydrology=hydro)
        terrain, _ = shore_terrain_material(world, HydrologyShoreKind.SEA)
        self.assertEqual(terrain, ReliefConditionTerrain.SHORE_SEA.value)

    def test_infer_kind_from_lake_neighbor(self) -> None:
        by_cell = {
            (1, 0): MapCellHydrology(role=HydrologyCellRole.SHORE),
            (0, 0): MapCellHydrology(role=HydrologyCellRole.LAKE),
        }
        self.assertEqual(infer_shore_kind((1, 0), by_cell), HydrologyShoreKind.LAKE)

    def test_column_fill_paints_lake_and_sea(self) -> None:
        heightmap = SurfaceHeightmap(
            world_uid="w-shore-paint",
            bbox=GridBBox(0, 2, 0, 0),
            surface_z={(0, 0): 1, (1, 0): 1, (2, 0): 1},
        )
        hydro = {
            (0, 0): MapCellHydrology.shore(HydrologyShoreKind.LAKE),
            (1, 0): MapCellHydrology(role=HydrologyCellRole.LAKE),
            (2, 0): MapCellHydrology.shore(HydrologyShoreKind.SEA),
        }
        cells = run_column_fill(
            _world(),
            heightmap,
            {(0, 0): 0, (1, 0): 0, (2, 0): 0},
            hydrology_by_cell=hydro,
            surface_terrain={(0, 0): "plains", (1, 0): "plains", (2, 0): "plains"},
        )
        by_xy = {(c.x, c.y): c for c in cells if c.z == 1}
        self.assertEqual(by_xy[(0, 0)].system_terrain, "shore_lake")
        self.assertEqual(by_xy[(2, 0)].system_terrain, "shore_sea")


class ShoreValidatorTest(unittest.TestCase):

    def test_normalize_accepts_category_defaults(self) -> None:
        out = normalize_world({
            "name": "Shore v2",
            "created_at": "2026-01-01T00:00:00",
            "hydrology": {"enabled": True},
        })
        rivers = out["hydrology"]["default_rivers"]["shore"]
        self.assertEqual(rivers["system_terrain"], "shore_river")

    def test_rejects_legacy_key_on_category_shore(self) -> None:
        with self.assertRaises(ImportValidationError) as ctx:
            normalize_world({
                "name": "Bad shore",
                "created_at": "2026-01-01T00:00:00",
                "hydrology": {
                    "default_lakes": {
                        "shore": {"system_terrain": "shore", "system_material": "sand"},
                    },
                },
            })
        codes = {err.code for err in ctx.exception.errors}
        self.assertIn("SHORE_CLASS_UNKNOWN", codes)


if __name__ == "__main__":
    unittest.main()
