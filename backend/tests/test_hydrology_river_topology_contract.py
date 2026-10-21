"""Review-debt R-1: one world resolution, explicit topology throughout rivers."""

import unittest
from unittest.mock import patch

from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology import hydrologyGeneratorService as facade
from app.application.worldData.generators.hydrology.autoresolve.proceduralRiverAutoresolve import autoresolve_river_segments
from app.application.worldData.generators.hydrology.riverNetworkAssembler import assemble_rivers
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import segments_from_declared
from app.application.worldData.generators.hydrology.rivers.resolveDeclaredRiverPath import resolve_declared_river_intents
from app.application.worldData.generators.hydrology.rivers.riverGeometry import distance_to_mouths, river_turn_ok
from app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner import (
    find_river_sources, plan_descent_path, plan_path_to_target, plan_river_network,
)
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import resolve_river_type_classify
from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import apply_declared_fine_river_carves
from app.application.worldData.generators.hydrology.types import DeclaredRiverEdge, HydrologyScope
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.hydrology_fixtures import flat_heightmap, hydro_master, hydro_topology, hydro_world


class RiverTopologyContractTests(unittest.TestCase):
    def test_entry_points_reject_omitted_and_none_topology_even_for_empty_input(self):
        hm = flat_heightmap(0, 1, 0, 1)
        world, master = hydro_world(), hydro_master()
        policy = resolve_river_type_classify(world)
        cases = (
            (segments_from_declared, ([],), {}),
            (find_river_sources, (hm, {}, policy), {"world_uid": world.world_uid}),
            (plan_descent_path, (hm, (0, 0), {}), {"policy": HydrologyRiversPolicy()}),
            (plan_path_to_target, (hm, (0, 0), (0, 0), {}), {"policy": HydrologyRiversPolicy()}),
            (plan_river_network, (world, hm, {}, policy), {}),
            (autoresolve_river_segments, (world, hm, master, {}), {}),
            (assemble_rivers, (world, hm, master), {}),
            (resolve_declared_river_intents, (world, hm, [], [], {}, policy),
             {"space": CoordinateSpace.WORLD_FINE_GRID}),
            (apply_declared_fine_river_carves, (world, [], {}), {}),
        )
        for function, args, kwargs in cases:
            with self.subTest(function=function.__name__, topology="omitted"):
                with self.assertRaises(TypeError):
                    function(*args, **kwargs)
            with self.subTest(function=function.__name__, topology=None):
                with self.assertRaises(TypeError):
                    function(*args, **kwargs, topology=None)
        with self.assertRaises(TypeError):
            river_turn_ok(None, [], (0, 0))
        with self.assertRaises(TypeError):
            distance_to_mouths(None, {}, ())

    def test_facade_resolves_world_topology_once_for_bodies_and_rivers(self):
        world = hydro_world(world_topology_mode=Mode.WRAPPED.value)
        hm = flat_heightmap(0, 3, 0, 2)
        with patch.object(facade, "resolve_hydrology_topology", wraps=facade.resolve_hydrology_topology) as resolve, \
                patch.object(facade, "assemble_water_bodies", wraps=facade.assemble_water_bodies) as water, \
                patch.object(facade, "assemble_rivers", wraps=facade.assemble_rivers) as rivers:
            facade.HydrologyGeneratorService().apply(world, [], hm, basin_specs=(),
                scopes=frozenset({HydrologyScope.LAKES, HydrologyScope.RIVERS}))
        resolve.assert_called_once()
        topology = water.call_args.args[2]
        self.assertIs(topology.mode, Mode.WRAPPED)
        self.assertIs(rivers.call_args.kwargs["topology"], topology)

    def test_facade_preserves_explicit_topology_without_resolving_again(self):
        hm = flat_heightmap(0, 3, 0, 2)
        topology = hydro_topology(hm, Mode.SPHERE)
        with patch.object(facade, "resolve_hydrology_topology") as resolve, \
                patch.object(facade, "assemble_rivers", wraps=facade.assemble_rivers) as rivers:
            facade.HydrologyGeneratorService().apply(hydro_world(), [], hm, topology=topology,
                scopes=frozenset({HydrologyScope.RIVERS}))
        resolve.assert_not_called()
        self.assertIs(rivers.call_args.kwargs["topology"], topology)

    def test_declared_assembler_keeps_wrapped_and_sphere_mouths(self):
        cases = (
            (Mode.WRAPPED, ((6, 1), (9, 1)),
             {(6, 1): 10, (7, 1): 8, (0, 1): 6, (1, 1): -2}, (1, 1)),
            (Mode.SPHERE, ((0, 1), (0, -2)),
             {(0, 1): 10, (0, 0): 8, (4, 0): 6, (4, 1): -2}, (4, 1)),
        )
        for mode, edge, elevations, mouth in cases:
            with self.subTest(mode=mode):
                hm = flat_heightmap(0, 7, 0, 3, z=50)
                hm.surface_z.update(elevations)
                topology = hydro_topology(hm, mode)
                occupied = {mouth: MapCellHydrology(water_body_uid="receiver", z_water_level=0)}
                world = hydro_world(hydrology=WorldHydrology(
                    default_rivers=HydrologyRiversPolicy(autoresolve=False)).model_dump(mode="json"))
                result = assemble_rivers(world, hm, hydro_master(declared_river_edges=[
                    DeclaredRiverEdge("river-edge", edge, "river")]), occupied, topology=topology,
                    water_bodies=(WaterBody(water_body_uid="receiver", kind=BasinKind.LAKE,
                                            declared_level=0, z_water_level=0),))
                self.assertEqual(set(result.by_cell), set(elevations) - {mouth})
                self.assertEqual(result.segments[0].polyline_cells[-1], mouth)
                self.assertEqual(hm.surface_z[mouth], elevations[mouth])


if __name__ == "__main__":
    unittest.main()
