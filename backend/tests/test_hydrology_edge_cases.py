"""Hydrology edge cases — declared / declared-autoresolve (intents) / autoresolve / consumers.

Plan: .cursor/plans/hydrology-edge-cases.md
Categories per master decision:
- declared            — master's explicit geometry, highest priority
- declared-autoresolve — declared intents (endpoints / via_locations) resolved procedurally
- autoresolve         — procedural fill, policy-gated only
"""

from tests.hydrology_fixtures import hydro_topology as _river_test_topology, heightmap_from_z as _river_test_heightmap
import unittest

from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.autoresolve.proceduralRiverAutoresolve import (
    autoresolve_river_segments,
)
from app.application.worldData.generators.hydrology.basins.coastalLandformClassifier import (
    classify_coastal_landforms,
)
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.hydrology.rivers.resolveDeclaredRiverPath import (
    resolve_declared_river_intents,
)
from app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner import (
    MAX_RIVERS_PER_BBOX,
)
from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import (
    apply_declared_fine_river_carves,
)
from app.application.worldData.generators.hydrology.types import (
    CoastlineSpec,
    HydrologyScope,
)
from app.dataModel.hydrology.rivers import RiverTypeClassify
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from tests.hydrology_fixtures import (
    flat_heightmap,
    heightmap_from_z,
    hydro_master,
    hydro_world,
    named_location,
    rivers_hydrology,
)


class TestDeclaredEdge(unittest.TestCase):
    """Master-declared geometry — highest priority."""

    def test_disabled_world_service_carves_nothing(self):
        hm = flat_heightmap(0, 10, 0, 6)
        before = dict(hm.surface_z)
        world = hydro_world(hydrology={"enabled": False})
        result = HydrologyGeneratorService().apply(world, [], hm)
        self.assertEqual(result.cell_index.by_cell, {})
        self.assertEqual(hm.surface_z, before)

    def test_no_declared_no_autoresolve_is_noop(self):
        hm = flat_heightmap(0, 10, 0, 6)
        before = dict(hm.surface_z)
        world = hydro_world(hydrology={
            "enabled": True,
            "default_seas": {
                "autoresolve_coastal_sea": False,
                "autoresolve_open_ocean": False,
            },
            "default_lakes": {"enabled": True, "autoresolve": False},
            "default_rivers": {"enabled": True, "autoresolve": False},
        })
        result = HydrologyGeneratorService().apply(world, [], hm)
        self.assertEqual(result.cell_index.by_cell, {})
        self.assertEqual(hm.surface_z, before)


class TestDeclaredAutoresolveEdge(unittest.TestCase):
    """Declared intents (endpoints / via_locations) resolved procedurally."""

    def _river_wire(self, **changes):
        wire = {
            "location_uid": "loc-river-via",
            "system_role": "stem",
            "declare_mode": "via_locations",
            "route_location_uids": ["loc-a", "loc-b"],
        }
        wire.update(changes)
        return wire

    def test_via_locations_carves_and_stamps_uid(self):
        world = hydro_world(hydrology={
            "enabled": True,
            "declared_rivers": [self._river_wire()],
        })
        locs = [named_location("loc-a", 3000, 2000),
                named_location("loc-b", 6000, 2000)]
        surface_z = {
            (gx, gy): 10
            for gx in range(2950, 6051)
            for gy in range(1950, 2051)
        }
        world.hydrology["default_rivers"] = {"max_path_cells": 6000 - 3000 + 1}
        hydro, _ = apply_declared_fine_river_carves(world, locs, surface_z,
            fine_hydro={(6000, 2000): MapCellHydrology(role=HydrologyCellRole.LAKE, water_body_uid="loc-b")},
            topology=_river_test_topology(_river_test_heightmap(surface_z)))
        self.assertTrue(hydro)
        self.assertTrue(all(
            e.water_body_uid == "loc-river-via" for e in hydro.values()))
        self.assertTrue(all(
            e.role == HydrologyCellRole.RIVER_BED for e in hydro.values()))

    def test_endpoints_mouth_snaps_to_nearest_water(self):
        world = hydro_world()
        surface_z = {
            (gx, gy): 10
            for gx in range(2000, 6001)
            for gy in range(1990, 2011)
        }
        hm = heightmap_from_z(surface_z)
        river = DeclaredRiver.model_validate({
            "location_uid": "loc-river-ep",
            "system_role": "stem",
            "declare_mode": "endpoints",
            "source": {"x": 2000, "y": 2000, "z": 0},
            "mouth": {"x": 5930, "y": 2000, "z": 0},
        })
        occupied = {
            (5950, 2000): MapCellHydrology(
                role=HydrologyCellRole.LAKE, water_body_uid="loc-lake"),
        }
        segments = resolve_declared_river_intents(
            world, hm, [river], [], occupied,
            resolve_river_type_classify(world),
            space=CoordinateSpace.WORLD_FINE_GRID,
            topology=_river_test_topology(hm),
        )
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].polyline_cells[-1], (5950, 2000))
        self.assertEqual(segments[0].location_uid, "loc-river-ep")

    def test_via_locations_missing_anchor_yields_nothing(self):
        world = hydro_world()
        hm = flat_heightmap(0, 10, 0, 10)
        river = DeclaredRiver.model_validate(self._river_wire())
        segments = resolve_declared_river_intents(
            world, hm, [river],
            [named_location("loc-a", 3, 3)],
            {},
            resolve_river_type_classify(world),
            space=CoordinateSpace.WORLD_FINE_GRID,
            topology=_river_test_topology(hm),
        )
        self.assertEqual(segments, [])

    def test_intent_river_classifies_mountain_on_steep_source(self):
        world = hydro_world()
        surface_z = {(gx, 5): 10 for gx in range(0, 11)}
        surface_z[(0, 5)] = 500
        hm = heightmap_from_z(surface_z)
        river = DeclaredRiver.model_validate({
            "location_uid": "loc-mtn-river",
            "system_role": "stem",
            "declare_mode": "endpoints",
            "source": {"x": 0, "y": 5, "z": 0},
            "mouth": {"x": 10, "y": 5, "z": 0},
        })
        segments = resolve_declared_river_intents(
            world, hm, [river], [], {},
            RiverTypeClassify(
                mountain_min_source_z=100,
                path_mountain_fraction=0.9,
                rapid_drop_threshold_m=50,
                mountain_bed_steepness_factor=2.0,
                foothill_gradient_threshold=0.5,
            ),
            space=CoordinateSpace.WORLD_FINE_GRID,
            topology=_river_test_topology(hm),
        )
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].connection_type, "mountain_river")
        self.assertEqual(segments[0].location_uid, "loc-mtn-river")


class TestAutoresolveEdge(unittest.TestCase):
    """Procedural fill — only when policy enables it."""

    def test_river_planner_respects_max_per_bbox(self):
        surface_z = {(gx, gy): 10 for gx in range(0, 24) for gy in range(0, 8)}
        for ridge_x in range(1, 24, 2):
            for gy in range(1, 8):
                surface_z[(ridge_x, gy)] = 10 + gy * 6
        occupied = {
            (gx, 0): MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN)
            for gx in range(0, 24)
        }
        world = hydro_world(hydrology=rivers_hydrology())
        segments = autoresolve_river_segments(
            world, heightmap_from_z(surface_z),
            hydro_master(scopes=frozenset({HydrologyScope.RIVERS})),
            occupied, topology=_river_test_topology(heightmap_from_z(surface_z)))
        self.assertGreater(len(segments), 0)
        self.assertLessEqual(len(segments), MAX_RIVERS_PER_BBOX)
        self.assertEqual(len(segments), MAX_RIVERS_PER_BBOX)


class TestConsumerEdge(unittest.TestCase):
    """Downstream consumers of hydrology output."""

    def test_landforms_scope_returns_declared_polylines(self):
        master = hydro_master(declared_coastline_specs=[
            CoastlineSpec(segments=[((2, 2), (8, 2))], location_uid="loc-sea")])
        landforms = classify_coastal_landforms(master)
        self.assertEqual(len(landforms.coastline_polylines), 1)
        self.assertIn((2, 2), landforms.coastline_polylines[0])
        self.assertIn((8, 2), landforms.coastline_polylines[0])
        self.assertEqual(landforms.islands, [])
        self.assertEqual(landforms.peninsulas, [])

    def test_scope_subset_does_not_run_coastal_sea(self):
        master = hydro_master(
            scopes=frozenset({HydrologyScope.LAKES}),
            declared_coastline_specs=[
                CoastlineSpec(
                    segments=[((2, 2), (8, 2))], location_uid="loc-sea")],
        )
        hm = flat_heightmap(0, 10, 0, 6)
        result = HydrologyGeneratorService().apply(
            hydro_world(), [], hm, master=master)
        self.assertEqual(result.cell_index.by_cell, {})


if __name__ == "__main__":
    unittest.main()
