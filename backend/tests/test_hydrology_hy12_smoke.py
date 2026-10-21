"""HY-12/6 acceptance: real coarse bake and declared → placement → relief → water → river."""

from tests.hydrology_fixtures import hydro_topology as _river_test_topology, heightmap_from_z as _river_test_heightmap
import unittest

from scripts.smoke_hydrology_hy12 import REPO, coarse_snapshot, load_fixture, render_svg
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import HydrologyGeneratorService
from app.application.worldData.generators.hydrology.placement import run_water_placement_pass
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinZ import apply_basin_z
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.topology.topologyGeometry import canonical_neighbors4
from tests.hydrology_fixtures import carve_then_fill, flat_heightmap, hydro_world


def basin_world(mode=Mode.WRAPPED, *, source="basin", level=5, floor=-8, river=False):
    hydro = {
        "enabled": True,
        "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
        "default_lakes": {"autoresolve": False},
        "default_rivers": {"autoresolve": False},
    }
    if source == "basin":
        hydro["declared_basins"] = [{
            "location_uid": "body", "kind": "lake", "floor_z": floor, "z_water_level": level,
            "rim": {"min": 1, "max": 2},
            "footprint": {"kind": "bbox", "x_min": 6, "x_max": 9, "y_min": 2, "y_max": 3},
        }]
    elif source == "lake":
        hydro["declared_lakes"] = [{"location_uid": "body", "shoreline": [
            {"x": x, "y": y, "z": 0} for x, y in ((2, 1), (5, 1), (5, 4), (2, 4))]}]
    else:
        hydro["declared_coastlines"] = [{"location_uid": "body", "kind": "sea", "path": [
            {"x": x, "y": y, "z": 0} for x, y in ((2, 1), (2, 4))]}]
    if river:
        hydro["declared_rivers"] = [{"location_uid": "river", "system_role": "stem",
            "declare_mode": "segments", "segments": [{"from": {"x": 4, "y": 2, "z": 0},
                "to": {"x": 0, "y": 2, "z": 0}, "connection_type": "river", "width_cells": 1}]}]
    return hydro_world(hydrology=hydro, fine_cells_per_map_cell=1, z_min=-30,
                       world_topology_mode=mode.value,
                       world_bounds={"x_min": 0, "x_max": 7, "y_min": 0, "y_max": 5})


class CoarseFixtureAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world, cls.locations = load_fixture(REPO / "fixtures/world_test_004.json")
        cls.snapshot = coarse_snapshot(cls.world, cls.locations)

    def test_fixture_contains_water_with_identity_and_per_body_level(self):
        wet = [cell for cell in self.snapshot["cells"] if (cell["hydrology"] or {}).get("liquid_candidate")]
        self.assertTrue(wet)
        self.assertTrue({-2, 2} <= {cell["x"] for cell in wet})
        self.assertIn("loc-geo-ocean-west-004", {cell["hydrology"]["water_body_uid"] for cell in wet})
        for cell in wet:
            self.assertLess(cell["z"], cell["hydrology"]["z_water_level"])

    def test_fixture_shores_are_dry_and_reference_materialized_bodies(self):
        bodies = {body["water_body_uid"]: body for body in self.snapshot["bodies"]}
        shores = [cell for cell in self.snapshot["cells"] if (cell["hydrology"] or {}).get("role") == "shore"]
        self.assertTrue(shores)
        for cell in shores:
            hydro = cell["hydrology"]
            self.assertFalse(hydro["liquid_candidate"])
            self.assertGreaterEqual(cell["z"], hydro["z_water_level"])
            self.assertEqual(hydro["z_water_level"], bodies[hydro["water_body_uid"]]["z_water_level"])

    def test_reserved_mountains_remain_dry_on_both_sides_of_water_seam(self):
        dry_raised = [cell for cell in self.snapshot["cells"] if cell["z"] > cell["base_z"]
                      and not (cell["hydrology"] or {}).get("liquid_candidate")]
        self.assertTrue(dry_raised)
        self.assertTrue({-2, 2} <= {cell["x"] for cell in dry_raised})

    def test_real_pipeline_replay_preserves_heights_roles_bodies_unions_and_rivers(self):
        self.assertEqual(self.snapshot, coarse_snapshot(self.world, self.locations))

    def test_diagnostic_render_uses_actual_floor_and_level(self):
        svg = render_svg(self.snapshot)
        self.assertIn("world-test-004", svg)
        self.assertIn("Post-carve floor / water level", svg)
        for cell in self.snapshot["cells"]:
            self.assertIn(f'z={cell["z"]}', svg)


class UnifiedWaterAcceptance(unittest.TestCase):
    def test_all_declared_sources_use_placement_relief_and_read_only_fill(self):
        for source in ("basin", "lake", "coastline"):
            with self.subTest(source=source):
                world = basin_world(source=source)
                hm = flat_heightmap(0, 7, 0, 5, z=20)
                placement = run_water_placement_pass(world, [], hm)
                self.assertTrue(placement.basin_specs)
                before = dict(hm.surface_z)
                apply_basin_z(hm, placement.basin_specs, placement.topology, reserved=frozenset())
                self.assertNotEqual(hm.surface_z, before)
                carved = dict(hm.surface_z)
                result = HydrologyGeneratorService().apply(world, [], hm,
                    basin_specs=placement.basin_specs, topology=placement.topology)
                self.assertEqual(hm.surface_z, carved)
                self.assertTrue(result.water_bodies)
                self.assertTrue(any(entry.liquid_candidate for entry in result.cell_index.by_cell.values()))
                self.assertEqual({body.water_body_uid for body in result.water_bodies}, {"body"})

    def test_wrapped_basin_keeps_uid_and_level_across_seam(self):
        hm = flat_heightmap(0, 7, 0, 5, z=20)
        result, carved = carve_then_fill(basin_world(), hm)
        wet = {cell: entry for cell, entry in result.cell_index.by_cell.items() if entry.liquid_candidate}
        self.assertEqual({x for x, _ in wet}, {0, 1, 6, 7})
        self.assertEqual({entry.water_body_uid for entry in wet.values()}, {"body"})
        self.assertEqual({entry.z_water_level for entry in wet.values()}, {5})
        self.assertEqual(hm.surface_z, carved)

    def test_planar_out_of_world_basin_is_rejected_without_clipping_or_expansion(self):
        hm = flat_heightmap(0, 7, 0, 5, z=20)
        keys = set(hm.surface_z)
        result, _ = carve_then_fill(basin_world(Mode.PLANAR), hm)
        wet = {cell for cell, entry in result.cell_index.by_cell.items() if entry.liquid_candidate}
        self.assertEqual(wet, set())
        self.assertEqual(result.water_bodies, ())
        self.assertEqual(set(hm.surface_z), keys)
        self.assertEqual(set(hm.surface_z.values()), {20})

    def test_sphere_basin_folds_and_derived_shore_uses_same_topology(self):
        world = basin_world(Mode.SPHERE)
        world.hydrology["declared_basins"][0]["footprint"] = {
            "kind": "bbox", "x_min": 0, "x_max": 1, "y_min": -2, "y_max": 0}
        hm = flat_heightmap(0, 7, 0, 5, z=20)
        placement = run_water_placement_pass(world, [], hm)
        result, _ = carve_then_fill(world, hm)
        wet = {cell for cell, entry in result.cell_index.by_cell.items() if entry.liquid_candidate}
        self.assertTrue({(0, 0), (4, 0)} <= wet)
        self.assertEqual(len(result.water_bodies), 1)
        for cell, entry in result.cell_index.by_cell.items():
            if entry.role is Role.SHORE:
                self.assertTrue(set(canonical_neighbors4(placement.topology, cell)) & wet)

    def test_river_stops_at_body_waterline_and_preserves_floor(self):
        world = basin_world(river=True)
        hm = flat_heightmap(0, 7, 0, 5, z=20)
        result, before_rivers = carve_then_fill(world, hm)
        self.assertEqual(len(result.river_segments), 1)
        path = result.river_segments[0].polyline_cells
        self.assertEqual(path, [(4, 2), (3, 2), (2, 2), (1, 2)])
        self.assertEqual(hm.surface_z[(1, 2)], before_rivers[(1, 2)])
        self.assertEqual(hm.surface_z[(0, 2)], before_rivers[(0, 2)])
        self.assertEqual(result.cell_index.by_cell[(1, 2)].water_body_uid, "body")
        self.assertEqual(result.waterfall_drops[-1].lower_z, 5)

    def test_fine_crossing_segments_apply_once_from_same_snapshot(self):
        from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import apply_declared_fine_river_carves
        world = basin_world(river=True)
        segment = world.hydrology["declared_rivers"][0]["segments"][0]
        world.hydrology["declared_rivers"][0]["segments"].append(dict(segment))
        _, z = apply_declared_fine_river_carves(world, [], {(x, 2): 20 for x in range(5)}, topology=_river_test_topology(_river_test_heightmap({(x, 2): 20 for x in range(5)})))
        self.assertEqual(z[(3, 2)], 17)


if __name__ == "__main__":
    unittest.main()
