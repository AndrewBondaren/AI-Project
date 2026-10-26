"""7b: registry hills, independent grade admission and explicit N+1 profile."""
from tests.planning.consumers.test_wiring import working_fixture
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.application.jsonValidation.terrainHillRegistry import terrain_with_hills
from app.application.worldData.generators.terrain.hills.hillPlacement import place_hills
from app.application.worldData.generators.terrain.landcover import finePaint
from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry
from app.application.worldData.generators.terrain.relief.sample.openLandTerrains import open_land_terrain_keys
from app.application.worldData.materialize.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.application.worldData.pack.refine.detailed.detailedGradeDiscover import discover_and_paint
from app.application.worldData.generators.terrain.types import ColumnRect
from app.dataModel.spatial.regionShape import BboxShape, EdgeNoise
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.dataModel.terrainMasks.regions import ForestSpec
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.wire.parentLightTile import ParentLightTile
from app.dataModel.worldPack.wire.worldMapCellWire import WorldMapCellWire
from app.ids.regionIdentity import region_uid
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from tests.planning.consumers.test_l0_l2 import frozen_surface_fixture
from tests.test_relief_grade_system_t3c import _open_template




def _steppe(**updates):
    return TerrainRegistryEntry.model_validate({
        "system_terrain": "steppe", "terrain_category": "solid", "merge_rank": 2,
        "supports_open_land_grade": True, "open_land_profile": "plains",
        "hills": {"min_spacing": 8, "radius": 2, "height": 2, "shapes": ["circle"]},
        **updates,
    })


class RegistryCutoverTests(unittest.TestCase):
    def test_grade_profile_contract_and_wire(self):
        for changes in (
            {"open_land_profile": None},
            {"open_land_profile": "unknown"},
            {"supports_open_land_grade": False},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                _steppe(**changes)
        self.assertEqual(TerrainRegistryEntry.model_validate(_steppe().model_dump()), _steppe())
        canonical = WorldTerrainRegistry.canonical_defaults()
        self.assertEqual(open_land_terrain_keys(), frozenset({"plains", "forest"}))
        self.assertEqual(canonical.entry_for("forest").open_land_profile, "forest")

    def test_no_hills_and_grade_admission_are_independent(self):
        for key, hills, enabled in (("steppe", None, True), ("basalt", HillPolicy(min_spacing=8, radius=2), False)):
            entry = _steppe(system_terrain=key, hills=hills,
                            supports_open_land_grade=enabled,
                            open_land_profile="plains" if enabled else None)
            registry = WorldTerrainRegistry([entry])
            world = SimpleNamespace(terrain_registry=registry.model_dump(mode="json"), world_uid="cutover")
            self.assertEqual(key in open_land_terrain_keys(world), enabled)
            z = {(x, y): 3 for x in range(32) for y in range(32)}
            place_hills(z, dict.fromkeys(z, key), {}, terrain_registry=registry, seed=1, z_min=0, z_max=20)
            self.assertEqual(any(v > 3 for v in z.values()), hills is not None)

    def test_legacy_hills_and_explicit_null_or_policy(self):
        world = SimpleNamespace(world_uid="cutover", terrain_registry=None,
                                terrain_masks={"default_plains": {"hills": {"radius": 3}}})
        self.assertEqual(terrain_with_hills(world).entry_for("plains").hills.radius, 3)
        for value in (None, {"radius": 7}):
            world.terrain_registry = [{"system_terrain": "plains", "terrain_category": "solid", "hills": value}]
            hills = terrain_with_hills(world).entry_for("plains").hills
            if value is None:
                self.assertIsNone(hills)
            else:
                self.assertEqual(hills.radius, 7)

    def test_legacy_alias_does_not_assign_hills_to_n_plus_one(self):
        world = SimpleNamespace(world_uid="cutover",
            terrain_registry=[_steppe(hills=None).model_dump(mode="json", exclude={"hills"})],
            terrain_masks={"default_plains": {"system_terrain": "steppe"}})
        self.assertIsNone(terrain_with_hills(world).entry_for("steppe").hills)

    def test_steppe_region_refine_and_grade_paint(self):
        registry = WorldTerrainRegistry(WorldTerrainRegistry.canonical_defaults().root + [_steppe()])
        spec = ForestSpec(name="converted", shape=BboxShape(x_min=0, y_min=0, x_max=31, y_max=31))
        masks = WorldTerrainMasks(declared_regions=[spec], default_landcover=LandcoverRegionsCategoryPolicy(
            autoresolve=False, seed_spacing=8, max_radius=16, claim_noise=EdgeNoise(amplitude=0, scale=4)))
        world = SimpleNamespace(
            world_uid="cutover", seed=1, world_topology_mode="planar",
            world_bounds={"x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0},
            fine_cells_per_map_cell=32, world_map_cells_per_tile=1, z_min=0, z_max=20,
            terrain_registry=registry.model_dump(mode="json"),
            terrain_masks=masks.model_dump(mode="json"), hydrology={"enabled": False},
            climate_zone_registry=None, relief_pick_policy=None,
        )
        uid = region_uid(world.world_uid, name=spec.name)
        parent = ParentLightTile.from_cells(world_uid=world.world_uid, gx=0, gy=0, side=1, tile_macro=32,
            cells=[WorldMapCellWire(tx=0, ty=0, surface_z=3, system_terrain="forest", region_uid=uid)])
        prepare = finePaint.prepare_landcover_inputs
        def with_state(ctx):
            return replace(prepare(ctx), state_snapshot={uid: StateSnapshotEntry("steppe")})
        # The caller's state-reader seam remains a stub until 9a; exercise its typed snapshot.
        with patch.object(finePaint, "prepare_landcover_inputs", side_effect=with_state):
            state = TerrainBatchOrchestrator().build_tile_surface_state(
                world, [], frozen_surface_fixture(world, parent), 0, 0, parent_light=parent,
                refine_policy=ParentLightRefinePolicy(z_band=0, detail_noise_amplitude=0), region_state_snapshot={uid: StateSnapshotEntry("steppe")}, working=working_fixture(world, frozen_surface_fixture(world, parent)))
        self.assertEqual(set(state.surface_terrain.values()), {"steppe"})
        self.assertEqual(set(state.surface_region_uid.values()), {uid})
        self.assertGreater(max(state.heightmap.surface_z.values()), 3)
        tpl_uid, template = _open_template()
        result, _, _ = discover_and_paint(world, state, ColumnRect(x_min=0, x_max=31, y_min=0, y_max=31), halo=0,
                                         catalog=None, templates={tpl_uid: template})
        self.assertTrue(result.grade_instances)
        self.assertEqual(set(state.surface_terrain.values()), {"steppe"})
        disabled = registry.entry_for("steppe").model_copy(update={
            "supports_open_land_grade": False, "open_land_profile": None})
        world.terrain_registry = WorldTerrainRegistry([disabled]).model_dump(mode="json")
        result, _, _ = discover_and_paint(world, state, ColumnRect(x_min=0, x_max=31, y_min=0, y_max=31), halo=0,
                                         catalog=None, templates={tpl_uid: template})
        self.assertFalse(result.grade_instances)


if __name__ == "__main__":
    unittest.main()
