"""Unit tests for procedural lake autoresolve — D HY-5b."""

import unittest

from app.application.jsonValidation.worldRow import hydrology
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.types import HydrologyScope
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from tests.hydrology_fixtures import (
    depression_heightmap as _depression_heightmap,
    hydro_master,
    hydro_world,
    lakes_hydrology,
)


def _world(**kwargs):
    kwargs.setdefault("hydrology", lakes_hydrology())
    return hydro_world(**kwargs)


class TestLakesPolicy(unittest.TestCase):

    def test_defaults_on(self):
        policy = hydrology(_world()).default_lakes
        self.assertIsInstance(policy, HydrologyLakesPolicy)
        self.assertTrue(policy.enabled)
        self.assertTrue(policy.autoresolve)

    def test_explicit_off(self):
        policy = hydrology(
            _world(hydrology={"enabled": True, "default_lakes": {"autoresolve": False}}),
        ).default_lakes
        self.assertFalse(policy.autoresolve)


class TestProceduralLakes(unittest.TestCase):

    def test_autoresolve_fills_existing_bowl_without_carve(self):
        hm = _depression_heightmap()
        before = dict(hm.surface_z)
        world = _world(world_topology_mode="planar", hydrology={
            **lakes_hydrology(), "default_seas": {"inland_sea_min_area_fraction": 1.0}})
        result = HydrologyGeneratorService().apply(world, [], hm, scopes=frozenset({HydrologyScope.LAKES}))
        self.assertTrue(result.water_bodies)
        self.assertEqual(hm.surface_z, before)
        self.assertTrue(all(body.water_body_uid.startswith("auto-lake-") for body in result.water_bodies))
        self.assertEqual({entry.water_body_uid for entry in result.cell_index.by_cell.values()},
                         {body.water_body_uid for body in result.water_bodies})

    def test_disabled_gates_do_not_fill_natural_bowl(self):
        cases = (
            ("global_off", WorldHydrology(enabled=False), HydrologyScope.LAKES),
            ("category_off", WorldHydrology(default_lakes=HydrologyLakesPolicy(enabled=False)), HydrologyScope.LAKES),
            ("autoresolve_off", WorldHydrology(default_lakes=HydrologyLakesPolicy(autoresolve=False)), HydrologyScope.LAKES),
            ("scope_off", WorldHydrology(), HydrologyScope.LANDFORMS),
        )
        for name, policy, scope in cases:
            with self.subTest(case=name):
                hm = _depression_heightmap()
                before = dict(hm.surface_z)
                world = _world(world_topology_mode="planar", hydrology=policy.model_dump(mode="json"))
                result = HydrologyGeneratorService().apply(world, [], hm, scopes=frozenset({scope}))
                self.assertEqual(result.water_bodies, ())
                self.assertEqual(result.cell_index.by_cell, {})
                self.assertEqual(hm.surface_z, before)

    def test_closed_global_minimum_has_no_guessed_high_lake_level(self):
        world = _world(world_topology_mode="wrapped")
        result = HydrologyGeneratorService().apply(world, [], _depression_heightmap(),
                                                   scopes=frozenset({HydrologyScope.LAKES}))
        self.assertEqual(result.water_bodies, ())


    def test_service_lakes_scope_without_declare(self):
        hm = _depression_heightmap()
        master = hydro_master(scopes=frozenset({HydrologyScope.LAKES}))
        # A high lake needs a finite physical outlet; wrapped global minima do
        # not acquire a guessed water level. Here the world rim supplies it.
        world = _world(world_topology_mode="planar", hydrology={
            **lakes_hydrology(), "default_seas": {"inland_sea_min_area_fraction": 1.0},
        })
        before = dict(hm.surface_z)
        result = HydrologyGeneratorService().apply(world, [], hm, master=master)
        roles = {entry.role for entry in result.cell_index.by_cell.values()}
        self.assertIn(HydrologyCellRole.LAKE, roles)
        self.assertEqual(hm.surface_z, before)


if __name__ == "__main__":
    unittest.main()
