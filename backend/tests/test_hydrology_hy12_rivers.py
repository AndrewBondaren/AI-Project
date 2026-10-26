"""HY-12/5: receiving waterline, shared topology, absolute river relief."""

from tests.hydrology_fixtures import hydro_topology as _river_test_topology, heightmap_from_z as _river_test_heightmap
from app.dataModel.topology.fineTopology import fine_topology
from app.application.worldData.generators.coordinates.convert import map_cell_fine_span
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.waterBody import WaterBody
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.application.worldData.generators.hydrology.riverNetworkAssembler import assemble_rivers
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_spec
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner import plan_descent_path
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import resolve_river_type_classify
from app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner import plan_river_network
from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import apply_declared_fine_river_carves
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.types import DeclaredRiverEdge, RiverSegment
from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinZ import apply_basin_z
from app.application.worldData.generators.terrain.reliefObjects.riverBed import apply_river_bed_z
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.topology.topologyGeometry import canonical_neighbors8
from tests.hydrology_fixtures import flat_heightmap, heightmap_from_z, hydro_master, hydro_topology, hydro_world


class RiverWaterlineTests(unittest.TestCase):
    def test_level_without_role_is_mouth_but_equal_level_is_dry(self):
        index = {(0, 0): MapCellHydrology(water_body_uid="lake", z_water_level=40)}
        self.assertTrue(is_river_mouth((0, 0), {(0, 0): 39}, index))
        self.assertFalse(is_river_mouth((0, 0), {(0, 0): 40}, index))
        self.assertFalse(is_river_mouth((1, 0), {(1, 0): -100}, index))
        self.assertFalse(is_river_mouth((0, 0), {(0, 0): -100}, {
            (0, 0): MapCellHydrology(z_water_level=40)}))

    def test_role_compatibility_and_roles_not_required_for_planning(self):
        hm = heightmap_from_z({(x, 0): 10 - x for x in range(5)})
        topology = hydro_topology(hm)
        raw = {(4, 0): MapCellHydrology(water_body_uid="lake", z_water_level=7)}
        painted = {(4, 0): MapCellHydrology(role=Role.LAKE, water_body_uid="lake", z_water_level=7)}
        expected = [(x, 0) for x in range(5)]
        self.assertEqual(plan_descent_path(hm, (0, 0), raw, topology=topology, policy=HydrologyRiversPolicy()), expected)
        self.assertEqual(plan_descent_path(hm, (0, 0), painted, topology=topology, policy=HydrologyRiversPolicy()), expected)
        self.assertTrue(is_river_mouth((4, 0), hm.surface_z, {(4, 0): MapCellHydrology(role=Role.LAKE)}))

    def test_wrapped_seam_turn_continues_in_same_direction(self):
        hm = flat_heightmap(0, 7, 0, 2, z=50)
        hm.surface_z.update({(6, 1): 10, (7, 1): 8, (0, 1): 6, (1, 1): -2})
        index = {(1, 1): MapCellHydrology(water_body_uid="sea", z_water_level=0)}
        self.assertEqual(plan_descent_path(hm, (6, 1), index, topology=hydro_topology(hm, Mode.WRAPPED), policy=HydrologyRiversPolicy()),
                         [(6, 1), (7, 1), (0, 1), (1, 1)])
        self.assertEqual(plan_descent_path(hm, (6, 1), index, topology=hydro_topology(hm), policy=HydrologyRiversPolicy()), [])

    def test_sphere_fold_continues_after_reflection(self):
        hm = flat_heightmap(0, 7, 0, 3, z=50)
        hm.surface_z.update({(0, 1): 10, (0, 0): 8, (4, 0): 6, (4, 1): -1})
        index = {(4, 1): MapCellHydrology(water_body_uid="sea", z_water_level=0)}
        self.assertEqual(plan_descent_path(hm, (0, 1), index, topology=hydro_topology(hm, Mode.SPHERE), policy=HydrologyRiversPolicy()),
                         [(0, 1), (0, 0), (4, 0), (4, 1)])

    def test_d8_domain_deduplicates_tiny_world(self):
        hm = flat_heightmap(0, 1, 0, 0)
        self.assertEqual(canonical_neighbors8(hydro_topology(hm, Mode.WRAPPED), (0, 0)), ((1, 0),))

    def test_profile_is_absolute_negative_and_stops_at_first_water(self):
        hm = heightmap_from_z({(0, 0): -1, (1, 0): -3, (2, 0): -10, (3, 0): -9})
        before = dict(hm.surface_z)
        segment = RiverSegment(list(hm.surface_z), "river")
        spec = river_bed_spec(hm, segment, depth_step=2, z_min=-20,
            occupied={(2, 0): MapCellHydrology(water_body_uid="sea", z_water_level=-5)})
        self.assertEqual(hm.surface_z, before)
        self.assertEqual(spec.bed_z, (((0, 0), -3), ((1, 0), -5)))
        apply_river_bed_z(hm, (spec,))
        once = dict(hm.surface_z)
        apply_river_bed_z(hm, (spec,))
        self.assertEqual(hm.surface_z, once)
        self.assertEqual(hm.surface_z[(2, 0)], -10)

    def test_assembler_retains_drop_and_mouth_floor(self):
        hm = heightmap_from_z({(0, 0): 30, (1, 0): 20, (2, 0): 5, (3, 0): 4})
        occupied = {(2, 0): MapCellHydrology(water_body_uid="lake", z_water_level=10)}
        result = assemble_rivers(hydro_world(z_min=-20), hm, hydro_master(declared_river_edges=[
            DeclaredRiverEdge("edge", ((0, 0), (3, 0)), "river")]), occupied,
               topology=hydro_topology(hm),
               water_bodies=(WaterBody(water_body_uid="lake", kind=BasinKind.LAKE,
                                       declared_level=10, z_water_level=10),),
           )
        self.assertEqual(result.segments[0].polyline_cells, [(0, 0), (1, 0), (2, 0)])
        self.assertEqual(set(result.by_cell), {(0, 0), (1, 0)})
        self.assertEqual([(drop.upper_z, drop.lower_z) for drop in result.drops], [(27, 17), (17, 10)])
        self.assertEqual(hm.surface_z[(2, 0)], 5)
        self.assertEqual(hm.surface_z[(3, 0)], 4)

    def test_carved_basin_fill_then_river_crosses_dry_shore(self):
        hm = flat_heightmap(0, 8, 0, 4, z=20)
        hm.surface_z.update({(1, 2): 30, (2, 2): 25})
        topology = hydro_topology(hm)
        spec = BasinSpec("lake", BasinKind.LAKE, "water",
                         frozenset({(5, 2), (6, 2)}), 20, 15, HydrologyBands(min=1, max=20))
        apply_basin_z(hm, (spec,), topology, reserved=frozenset())
        water = assemble_water_bodies(hm, (spec,), topology, WorldHydrology(),
                                     change_uid="test", auto_seas=False, auto_lakes=False)
        index = water.materialized.by_cell
        self.assertEqual(index[(4, 2)].role, Role.SHORE)
        path = plan_descent_path(hm, (1, 2), index, topology=topology, policy=HydrologyRiversPolicy())
        self.assertTrue(path)
        self.assertEqual(path[-1], (5, 2))
        self.assertIn((4, 2), path)
        network = plan_river_network(hydro_world(), hm, index,
                                     resolve_river_type_classify(hydro_world()), topology=topology)
        self.assertTrue(any(index.get(cell) is not None and index[cell].role is Role.SHORE
                            for route in network for cell in route[:-1]))

    def test_fine_rivers_sample_coarse_z_and_preserve_receiving_water(self):
        world = hydro_world(fine_cells_per_map_cell=2, z_min=-20, hydrology={
            "enabled": True, "declared_rivers": [{
                "location_uid": "river", "system_role": "stem", "declare_mode": "segments",
                "segments": [{"from": {"x": 0, "y": 0, "z": 0},
                              "to": {"x": 5, "y": 0, "z": 0},
                              "connection_type": "river", "width_cells": 1}],
            }]})
        hydro, elevations = apply_declared_fine_river_carves(world, [],
            {(0, 0): 10, (1, 0): 5, (2, 0): -10},
            base_space=CoordinateSpace.WORLD_SURFACE_GRID,
            coarse_hydro={(2, 0): MapCellHydrology(role=Role.LAKE, water_body_uid="lake", z_water_level=0)}, topology=fine_topology(_river_test_topology(_river_test_heightmap({(0, 0): 10, (1, 0): 5, (2, 0): -10})), map_cell_fine_span(world)))
        self.assertEqual(set(hydro), {(x, 0) for x in range(4)})
        self.assertEqual(elevations[(3, 0)], 2)
        self.assertEqual(elevations[(4, 0)], -10)

    def test_pipeline_supplies_pre_river_elevation_to_fine_profiles(self):
        from tests.planning.consumers.test_wiring import Composition, capture, world
        from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
        from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
        from app.application.cancellation.requestPlanWait import RequestPlanWait
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        source = world(world_bounds=dict(x_min=0, x_max=3, y_min=0, y_max=2),
            world_topology_mode="planar", z_min=-100, z_max=1, hydrology={"enabled": True,
                "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
                "default_lakes": {"autoresolve": False},
                "default_rivers": {"autoresolve": False, "mouth_search_radius_fine": 0},
                "declared_basins": [{"location_uid": "basin", "kind": "ocean", "floor_z": -10,
                    "footprint": {"kind": "bbox", "x_min": 0, "x_max": 10, "y_min": 0, "y_max": 20}}],
                "declared_rivers": [{"location_uid": "river", "declare_mode": "segments", "segments": [
                    {"from": {"x": 35, "y": 5}, "to": {"x": 5, "y": 5},
                     "connection_type": "river", "width_cells": 2}]}]})
        source.map_settings = {"global_cell_size_m": 10}
        from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
        original = FineRiverPlanner.plan
        with patch.object(FineRiverPlanner, "plan", autospec=True, side_effect=original) as fine:
            _, working = SurfacePlanningEntry(composition.assembler, SurfacePlanningCapture()).require_plan_inputs(
                source, [], wait=RequestPlanWait.unbounded())
        bundle = composition.prepare(capture(source))
        self.assertTrue(bundle.river_relief.payload.coarse_beds)
        self.assertTrue(working.hydrology.fine_z_overrides)
        self.assertEqual(fine.call_args.kwargs["surface_z"], bundle.relief.payload.surface_z)
        self.assertNotEqual(bundle.relief.payload.surface_z, bundle.hydrology.payload.coarse_surface_z,
            "fine routing must sample pre-river heights even when coarse river beds changed them")


if __name__ == "__main__":
    unittest.main()
