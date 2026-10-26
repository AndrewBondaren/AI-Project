"""HY-12/3b: pre-1.4 water placement pass wiring + one-carve cutover smoke."""

import json
import unittest
from tests.planning.consumers.test_wiring import planning_kwargs
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import (
    resolve_hydrology_topology,
)
from app.application.worldData.generators.hydrology.placement import run_water_placement_pass
from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
from app.application.worldData.generators.terrain.reliefObjects import apply_relief_objects_z
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.db.models.namedLocation import NamedLocation
from tests.hydrology_fixtures import flat_heightmap, hydro_world

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_test_004.json"


def _fixture_world_and_locations():
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    world = hydro_world(**({"z_min": None} | {k: v for k, v in bundle["world"].items()
                                             if k != "world_uid"}),
                        world_uid=bundle["world"]["world_uid"])
    from app.db.models.world import World
    row = World(world_uid=world.world_uid, name="fixture", created_at="")
    for key, value in vars(world).items():
        setattr(row, key, value)
    world = row
    known = {f.name for f in fields(NamedLocation)}
    locations = [NamedLocation(**{k: v for k, v in row.items() if k in known})
                 for row in bundle["locations"]]
    return world, locations


def _basin_world() -> SimpleNamespace:
    return hydro_world(
        hydrology={
            "enabled": True,
            "default_lakes": {"autoresolve": False},
            "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
            "declared_basins": [{
                "location_uid": "basin-a", "kind": "ocean", "floor_z": -10,
                "footprint": {"kind": "bbox", "x_min": 2000, "x_max": 4000,
                              "y_min": 2000, "y_max": 4000},
            }],
        },
        fine_cells_per_map_cell=1000,
        z_min=-100,
    )


def _pole():
    pole = MagicMock()
    pole.sample.return_value = SimpleNamespace(typical_elevation_z=0)
    return pole


class WaterPlacementPassUnitTests(unittest.TestCase):
    def test_no_declared_sources_returns_none(self):
        world = hydro_world(hydrology={"enabled": True})
        self.assertIsNone(run_water_placement_pass(world, [], flat_heightmap(0, 10, 0, 6)))

    def test_projected_basin_produces_specs_and_single_carve(self):
        world = _basin_world()
        hm = flat_heightmap(0, 10, 0, 6)
        result = run_water_placement_pass(world, [], hm)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.basin_specs), 1)
        footprint = result.basin_specs[0].footprint
        self.assertIn((3, 3), footprint)
        apply_relief_objects_z(world, [], hm, pole_field=_pole(),
                               basin_specs=result.basin_specs, topology=result.topology)
        self.assertTrue(all(hm.surface_z[cell] < 0 for cell in footprint))
        carved = dict(hm.surface_z)
        HydrologyGeneratorService().apply(world, [], hm)
        self.assertEqual(hm.surface_z, carved)  # one carve: legacy apply does not rewrite z

    def test_declared_projection_collapse_is_reported_not_fatal(self):
        world = hydro_world(
            hydrology={
                "enabled": True,
                "default_lakes": {"autoresolve": False},
                "default_seas": {"autoresolve_coastal_sea": False,
                                 "autoresolve_open_ocean": False},
                "declared_basins": [
                    {"location_uid": "ok", "kind": "ocean", "floor_z": -10,
                     "footprint": {"kind": "bbox", "x_min": 2000, "x_max": 4000,
                                   "y_min": 2000, "y_max": 4000}},
                    {"location_uid": "tiny", "kind": "ocean", "floor_z": -10,
                     "footprint": {"kind": "polygon",
                                   "vertices": [[0, 0], [1, 0], [1, 1]]}},
                ],
            },
            fine_cells_per_map_cell=1000,
            z_min=-100,
        )
        result = run_water_placement_pass(world, [], flat_heightmap(0, 10, 0, 6))
        self.assertIsNotNone(result)
        self.assertEqual([spec.source_uid for spec in result.basin_specs], ["ok"])


class WaterPlacementPassFixtureTests(unittest.TestCase):
    def test_world_test_004_wrapped_ocean_basin_carves_across_seam(self):
        world, locations = _fixture_world_and_locations()
        policy = WorldHydrology.model_validate(world.hydrology)
        # The fixture intentionally duplicates location_uid between a declared basin and
        # a declared coastline; runtime merges them with one structured warning.
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as log:
            deps = planning_kwargs(self)
            _, working = SurfacePlanningEntry(deps["planning"], deps["capture"]).require_plan_inputs(
                world, locations, wait=deps["wait"])
        self.assertTrue(any("WATER_PLACEMENT_MERGED_SOURCES" in line
                            and "loc-geo-ocean-west-004" in line for line in log.output))
        self.assertIsNotNone(working)
        projected = policy.declared_basins[0].footprint.projected(1000)
        topology = working.landcover.topology
        x0, y0, x1, y1 = projected.bbox()
        footprint = {
            cell
            for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
            if projected.contains(x, y)
            and (cell := topology.canonicalize(x, y)) in working.hydrology.coarse_surface_z
        }
        self.assertTrue(footprint)
        self.assertIn(-2, {x for x, _ in footprint})
        self.assertIn(2, {x for x, _ in footprint})  # crosses the wrapped x-seam
        carved = {cell for cell in footprint
                  if working.hydrology.coarse_surface_z[cell] < policy.default_water_level}
        self.assertTrue(carved)
        # HY-12/4: materialized water carries the effective per-body level and
        # identity on both sides of the seam; bottom z is not the water surface.
        water_cells = {cell: entry for cell, entry in working.hydrology.coarse_hydro.items()
                       if entry.role is not None and entry.role.is_open_water_role()}
        self.assertTrue(water_cells)
        self.assertTrue({-2, 2} <= {x for x, _ in water_cells})
        self.assertIn("loc-geo-ocean-west-004", {entry.water_body_uid for entry in water_cells.values()})
        for cell, entry in water_cells.items():
            self.assertIsNotNone(entry.z_water_level)
            self.assertLess(working.hydrology.coarse_surface_z[cell], entry.z_water_level)
        # The rest are mountain-reserved cells (raised in 1.4 before basinZ).
        for cell in footprint - carved:
            self.assertNotEqual(working.hydrology.coarse_surface_z[cell], working.terrain.relief_z[cell])

    def test_world_test_004_pass_is_deterministic(self):
        world, locations = _fixture_world_and_locations()
        deps = planning_kwargs(self)
        entry = SurfacePlanningEntry(deps["planning"], deps["capture"])
        _, first = entry.require_plan_inputs(world, locations, wait=deps["wait"])
        _, second = entry.require_plan_inputs(world, locations, wait=deps["wait"])
        self.assertEqual(first.hydrology.coarse_surface_z, second.hydrology.coarse_surface_z)
        self.assertEqual(first.hydrology.coarse_hydro, second.hydrology.coarse_hydro)



if __name__ == "__main__":
    unittest.main()
