"""water_body_uid stamps on every hydrology carve path — review-debt-7plus step 3."""

from tests.hydrology_fixtures import hydro_topology as _river_test_topology, heightmap_from_z as _river_test_heightmap
import unittest

from tests.hydrology_geometry_helpers import apply_test_river
from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import (
    apply_declared_fine_river_carves,
)
from app.application.worldData.generators.hydrology.types import (
    RiverSegment,
)
from app.application.worldData.generators.terrain.passes.columnFillPass import run_column_fill
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import (
    MapCellHydrology,
    dump_cell_hydrology,
    parse_cell_hydrology,
)
from tests.hydrology_fixtures import (
    depression_heightmap as _depression_heightmap,
    flat_heightmap as _flat_heightmap,
    hydro_world,
    seas_lakes_hydrology,
)


def _world(**kwargs):
    kwargs.setdefault("hydrology", seas_lakes_hydrology())
    return hydro_world(**kwargs)


class WaterBodyUidTests(unittest.TestCase):

    def test_declared_body_and_shore_keep_location_uid_for_each_source(self):
        from tests.test_hydrology_hy12_smoke import basin_world
        from tests.hydrology_fixtures import carve_then_fill
        for source in ("basin", "lake", "coastline"):
            with self.subTest(source=source):
                result, _ = carve_then_fill(basin_world(source=source), _flat_heightmap(0, 7, 0, 5, z=20))
                self.assertTrue(result.cell_index.by_cell)
                self.assertEqual({entry.water_body_uid for entry in result.cell_index.by_cell.values()}, {"body"})
                self.assertEqual(result.water_bodies[0].location_uid, "body")

    def test_disconnected_declared_bodies_keep_distinct_uids(self):
        from tests.test_hydrology_hy12_smoke import basin_world
        from tests.hydrology_fixtures import carve_then_fill
        world = basin_world()
        world.hydrology["declared_basins"] = [
            {"location_uid": uid, "kind": "lake", "floor_z": -8, "z_water_level": 5,
             "footprint": {"kind": "bbox", "x_min": lo, "x_max": hi, "y_min": 1, "y_max": 2}}
            for uid, lo, hi in (("left", 0, 1), ("right", 4, 5))]
        result, _ = carve_then_fill(world, _flat_heightmap(0, 7, 0, 5, z=20))
        self.assertEqual({body.water_body_uid for body in result.water_bodies}, {"left", "right"})
        self.assertEqual(result.physical_unions, ())

    def test_natural_body_identity_replays_without_recarving(self):
        from app.application.worldData.generators.hydrology.hydrologyGeneratorService import HydrologyGeneratorService
        from app.application.worldData.generators.hydrology.types import HydrologyScope
        world = _world(world_topology_mode="planar", hydrology={
            **seas_lakes_hydrology(), "default_seas": {"inland_sea_min_area_fraction": 1.0}})
        hm = _depression_heightmap()
        first = HydrologyGeneratorService().apply(world, [], hm, scopes=frozenset({HydrologyScope.LAKES}))
        second = HydrologyGeneratorService().apply(world, [], hm, scopes=frozenset({HydrologyScope.LAKES}))
        self.assertTrue(first.water_bodies)
        self.assertEqual(first.water_bodies, second.water_bodies)
        self.assertEqual(first.cell_index.by_cell, second.cell_index.by_cell)


    def test_river_declared_and_auto_identity(self):
        hm = _flat_heightmap(0, 5, 0, 5)
        declared = RiverSegment(polyline_cells=[(1, 1), (2, 1), (3, 1)],
                                connection_type="river", edge_uid="e1",
                                location_uid="loc-river", declared=True)
        carved = apply_test_river(hm, declared, depth_step=1, z_min=world_z_min(_world()))
        self.assertTrue(carved)
        self.assertTrue(all(e.water_body_uid == "loc-river" for e in carved.values()))
        self.assertTrue(all(e.connection_edge_uid == "e1" for e in carved.values()))
        auto = apply_test_river(
            _flat_heightmap(0, 5, 0, 5),
            RiverSegment(polyline_cells=[(1, 1), (2, 1), (3, 1)], connection_type="river"),
            depth_step=1, z_min=world_z_min(_world()))
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
        w.hydrology["default_rivers"] = {"max_path_cells": len(surface_z)}
        hydro, _ = apply_declared_fine_river_carves(w, [], surface_z,
            fine_hydro={(6000, 9000): MapCellHydrology(role=HydrologyCellRole.LAKE, water_body_uid="lake")},
            topology=_river_test_topology(_river_test_heightmap(surface_z)))
        self.assertTrue(hydro)
        self.assertTrue(all(e.water_body_uid == "loc-river" for e in hydro.values()))


    def test_endpoints_river_fine_carve_stamps_uid(self):
        w = _world(hydrology={
            "enabled": True,
            "declared_rivers": [{
                "location_uid": "loc-river-ep",
                "system_role": "stem",
                "declare_mode": "endpoints",
                "source": {"x": 2000, "y": 2000, "z": 0},
                "mouth": {"x": 6000, "y": 2000, "z": 0},
            }],
        })
        surface_z = {
            (gx, gy): 10
            for gx in range(2000, 6001)
            for gy in range(1950, 2051)
        }
        w.hydrology["default_rivers"] = {"max_path_cells": 6000 - 2000 + 1}
        hydro, _ = apply_declared_fine_river_carves(w, [], surface_z,
            fine_hydro={(6000, 2000): MapCellHydrology(role=HydrologyCellRole.LAKE, water_body_uid="lake")},
            topology=_river_test_topology(_river_test_heightmap(surface_z)))
        self.assertTrue(hydro)
        self.assertTrue(all(e.water_body_uid == "loc-river-ep" for e in hydro.values()))

    def test_column_fill_persists_water_body_uid(self):
        heightmap = _flat_heightmap(0, 2, 0, 0, z=1)
        hydro = {
            (1, 0): MapCellHydrology(
                role=HydrologyCellRole.LAKE, water_body_uid="loc-lk"),
        }
        cells = run_column_fill(
            _world(),
            heightmap,
            {(0, 0): 0, (1, 0): 0, (2, 0): 0},
            hydrology_by_cell=hydro,
            surface_terrain={(0, 0): "plains", (1, 0): "plains", (2, 0): "plains"},
        )
        by_xy = {(c.x, c.y): c for c in cells if c.z == 1}
        self.assertEqual(by_xy[(1, 0)].hydrology["water_body_uid"], "loc-lk")

    def test_wire_round_trip_and_missing_default(self):
        dumped = dump_cell_hydrology(MapCellHydrology(
            role=HydrologyCellRole.LAKE, water_body_uid="x"))
        self.assertEqual(dumped["water_body_uid"], "x")
        self.assertIsNone(parse_cell_hydrology({"role": "lake"}).water_body_uid)
        bare = dump_cell_hydrology(MapCellHydrology(role=HydrologyCellRole.LAKE))
        self.assertNotIn("water_body_uid", bare)


if __name__ == "__main__":
    unittest.main()
