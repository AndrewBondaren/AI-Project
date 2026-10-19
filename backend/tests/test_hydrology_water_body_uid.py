"""water_body_uid stamps on every hydrology carve path — review-debt-7plus step 3."""

import unittest
from types import SimpleNamespace

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.autoresolve.proceduralLakeAutoresolve import (
    autoresolve_lakes,
)
from app.application.worldData.generators.hydrology.autoresolve.proceduralSeaAutoresolve import (
    autoresolve_sea_basins,
)
from app.application.worldData.generators.hydrology.basins.lakeBasinGenerator import (
    _resolve_interior,
    carve_lake_basin,
)
from app.application.worldData.generators.hydrology.basins.oceanBasinGenerator import (
    expand_open_ocean,
)
from app.application.worldData.generators.hydrology.basins.seaBasinGenerator import (
    generate_coastal_sea,
)
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.load.resolveHydrologyBands import (
    resolve_hydrology_bands,
)
from app.application.worldData.generators.hydrology.rivers.riverBedCarver import carve_river_segment
from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import (
    apply_declared_fine_river_carves,
)
from app.application.worldData.generators.hydrology.types import (
    CoastlineSpec,
    HydrologyBands,
    HydrologyMasterInput,
    HydrologyScope,
    LakeSpec,
    LoadedConnectionGraph,
    RiverSegment,
)
from app.application.worldData.generators.hydrology.waterBodyIdentity import (
    AutoWaterBodyRole,
    auto_water_body_uid,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import (
    MapCellHydrology,
    dump_cell_hydrology,
    parse_cell_hydrology,
)


def _world(**kwargs):
    defaults = {
        "world_uid": "test-world",
        "hydrology": {
            "enabled": True,
            "default_seas": {
                "bands": {"min": 1, "max": 2},
                "autoresolve_coastal_sea": True,
                "autoresolve_open_ocean": True,
            },
            "default_lakes": {
                "enabled": True,
                "autoresolve": True,
                "bands": {"min": 1, "max": 4},
            },
        },
        "fine_cells_per_map_cell": 3000,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _heightmap(surface_z: dict[tuple[int, int], int]) -> SurfaceHeightmap:
    xs = [gx for gx, _ in surface_z]
    ys = [gy for _, gy in surface_z]
    return SurfaceHeightmap(
        world_uid="test-world",
        bbox=GridBBox(min(xs), max(xs), min(ys), max(ys)),
        surface_z=dict(surface_z),
    )


def _flat_heightmap(gx_lo: int, gx_hi: int, gy_lo: int, gy_hi: int, z: int = 5) -> SurfaceHeightmap:
    return _heightmap({
        (gx, gy): z
        for gx in range(gx_lo, gx_hi + 1)
        for gy in range(gy_lo, gy_hi + 1)
    })


def _depression_heightmap() -> SurfaceHeightmap:
    surface_z: dict[tuple[int, int], int] = {}
    for gx in range(0, 11):
        for gy in range(0, 11):
            ring = max(abs(gx - 5), abs(gy - 5))
            if ring == 0:
                surface_z[(gx, gy)] = 7950
            elif ring == 1:
                surface_z[(gx, gy)] = 8000
            elif ring <= 3:
                surface_z[(gx, gy)] = 8010
            else:
                surface_z[(gx, gy)] = 8050
    return _heightmap(surface_z)


def _master(**changes):
    return HydrologyMasterInput(
        world_uid="test-world",
        hydrology_enabled=True,
        scopes=frozenset(HydrologyScope),
        connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
        **changes,
    )


SQUARE = [((3, 3), (7, 3)), ((7, 3), (7, 7)), ((7, 7), (3, 7)), ((3, 7), (3, 3))]


class WaterBodyUidTests(unittest.TestCase):

    def test_declared_lake_cells_carry_location_uid(self):
        hm = _flat_heightmap(0, 10, 0, 10)
        spec = LakeSpec(shoreline_segments=SQUARE, location_uid="loc-lake")
        carved = carve_lake_basin(hm, spec, HydrologyBands(min=1, max=3))
        self.assertTrue(carved)
        self.assertTrue(all(e.water_body_uid == "loc-lake" for e in carved.values()))
        shore = [e for e in carved.values() if e.role == HydrologyCellRole.SHORE]
        self.assertTrue(shore)
        self.assertTrue(all(e.water_body_uid == "loc-lake" for e in shore))

    def test_lake_spec_without_location_uid_falls_back_to_auto(self):
        hm = _flat_heightmap(0, 10, 0, 10)
        spec = LakeSpec(shoreline_segments=SQUARE)
        shoreline = rasterize_segments(spec.shoreline_segments)
        interior = _resolve_interior(hm, spec.shoreline_segments, shoreline)
        expected = auto_water_body_uid(AutoWaterBodyRole.LAKE, min(interior))
        carved = carve_lake_basin(hm, spec, HydrologyBands(min=1, max=3))
        self.assertTrue(carved)
        uids = {e.water_body_uid for e in carved.values()}
        self.assertEqual(uids, {expected})

    def test_autoresolve_lakes_use_feature_center_and_are_deterministic(self):
        runs = []
        for _ in range(2):
            carved, _ = autoresolve_lakes(_world(), _depression_heightmap(), _master(), {})
            runs.append({cell: e.water_body_uid for cell, e in carved.items()})
        self.assertTrue(runs[0])
        self.assertTrue(all(uid.startswith("auto-lake-") for uid in runs[0].values()))
        self.assertEqual(runs[0], runs[1])

    def test_declared_coastline_and_ocean_relabel_share_uid(self):
        master = _master(declared_coastline_specs=[
            CoastlineSpec(segments=[((2, 2), (8, 2))], location_uid="loc-sea")])
        carved, _ = generate_coastal_sea(_world(), _flat_heightmap(0, 10, 0, 6), master)
        self.assertTrue(carved)
        self.assertTrue(all(e.water_body_uid == "loc-sea" for e in carved.values()))
        ocean, _ = expand_open_ocean(_flat_heightmap(0, 10, 0, 6), carved)
        self.assertTrue(ocean)
        self.assertTrue(all(e.role == HydrologyCellRole.OPEN_OCEAN for e in ocean.values()))
        self.assertTrue(all(e.water_body_uid == "loc-sea" for e in ocean.values()))

    def test_sea_autoresolve_without_declare_is_one_body(self):
        maps = []
        for _ in range(2):
            auto, _ = autoresolve_sea_basins(
                _world(), _flat_heightmap(0, 10, 0, 6), _master(), {},
                autoresolve_coastal=True, autoresolve_open_ocean=True)
            maps.append({cell: e.water_body_uid for cell, e in auto.items()})
        self.assertTrue(maps[0])
        uids = set(maps[0].values())
        self.assertEqual(len(uids), 1)
        self.assertTrue(next(iter(uids)).startswith("auto-sea-"))
        self.assertEqual(maps[0], maps[1])

    def test_river_declared_and_auto_identity(self):
        hm = _flat_heightmap(0, 5, 0, 5)
        declared = RiverSegment(polyline_cells=[(1, 1), (2, 1), (3, 1)],
                                connection_type="river", edge_uid="e1",
                                location_uid="loc-river", declared=True)
        carved = carve_river_segment(hm, declared, depth_step=1)
        self.assertTrue(carved)
        self.assertTrue(all(e.water_body_uid == "loc-river" for e in carved.values()))
        self.assertTrue(all(e.connection_edge_uid == "e1" for e in carved.values()))
        auto = carve_river_segment(
            _flat_heightmap(0, 5, 0, 5),
            RiverSegment(polyline_cells=[(1, 1), (2, 1), (3, 1)], connection_type="river"),
            depth_step=1)
        self.assertTrue(all(e.water_body_uid == "auto-river-1x1" for e in auto.values()))

    def test_fine_river_carve_stamps_uid(self):
        w = _world(hydrology={
            "enabled": True,
            "declared_rivers": [{
                "location_uid": "loc-river",
                "system_role": "stem",
                "declare_mode": "segments",
                "segments": [{
                    "from": {"x": 3000, "y": 9000, "z": 0},
                    "to": {"x": 6000, "y": 9000, "z": 0},
                    "connection_type": "river",
                    "width_cells": 1,
                }],
            }],
        })
        surface_z = {(gx, 9000): 10 for gx in range(3000, 6001)}
        hydro, _ = apply_declared_fine_river_carves(w, [], surface_z)
        self.assertTrue(hydro)
        self.assertTrue(all(e.water_body_uid == "loc-river" for e in hydro.values()))

    def test_wire_round_trip_and_missing_default(self):
        dumped = dump_cell_hydrology(MapCellHydrology(
            role=HydrologyCellRole.LAKE, water_body_uid="x"))
        self.assertEqual(dumped["water_body_uid"], "x")
        self.assertIsNone(parse_cell_hydrology({"role": "lake"}).water_body_uid)
        bare = dump_cell_hydrology(MapCellHydrology(role=HydrologyCellRole.LAKE))
        self.assertNotIn("water_body_uid", bare)


if __name__ == "__main__":
    unittest.main()
