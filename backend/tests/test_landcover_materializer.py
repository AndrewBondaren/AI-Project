"""Standalone 5b acceptance; no contributor, manifest or SQL wiring."""

from dataclasses import replace
from itertools import permutations
from types import SimpleNamespace
import unittest

from pydantic import ValidationError

from app.application.worldData.generators.terrain.landcover.autoresolve.claim import fine_topology
from app.application.worldData.generators.terrain.landcover.autoresolve.mergeSublocations import CoverageSeed, merge_sublocations
from app.application.worldData.generators.terrain.landcover.autoresolve.seedGrid import WorldSeed, generate_seeds
from app.application.worldData.generators.terrain.landcover.hydrologyIndex import HydroIndexStatus, index_hydrology
from app.application.worldData.generators.terrain.landcover.materializer import LandcoverMaterializer
from app.application.worldData.generators.terrain.landcover.types import AnchoredRegion, LandcoverInputs, RegionSource, StateSnapshotEntry
from app.application.worldData.masks.regionRasterContext import RegionRasterContext
from app.application.worldData.masks.regionRasterizer import rasterize_claim_fine, rasterize_fine
from app.application.worldData.masks.runMaskDomain import run_mask_domain
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.regions.regionFacts import ClimateFacts, RegionFacts
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.spatial.regionShape import AnchorRadiusShape, BboxShape, EdgeNoise
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.enums.eligibilityOp import EligibilityOp
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.dataModel.terrainMasks.regions import ForestSpec, PlainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.wire.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexWire
from app.dataModel.worldPack.wire.worldBounds import WorldBounds
from app.dataModel.worldPack.wire.worldTopology import WorldTopology
from app.dataModel.worldPack.wire.worldTopologyMode import WorldTopologyMode
from app.ids.regionIdentity import region_uid


class LandcoverMaterializerTests(unittest.TestCase):
    def setUp(self):
        self.policy = LandcoverRegionsCategoryPolicy(seed_spacing=4, max_radius=7,
                                                    claim_noise=EdgeNoise(amplitude=2, scale=3))
        self.scale = LightGridScale.from_tile(8, 4)
        self.topology = WorldTopology(mode=WorldTopologyMode.PLANAR,
                                      bounds=WorldBounds(x_min=0, x_max=1, y_min=0, y_max=1))
        self.registry = WorldTerrainRegistry.canonical_defaults()
        self.forest, self.plains = self.registry.forest_terrain_key(), self.registry.plains_terrain_key()
        self.world = SimpleNamespace(world_uid="landcover-tests", terrain_registry=self.registry.model_dump(mode="json"),
                                     terrain_masks=WorldTerrainMasks(default_landcover=self.policy).model_dump(mode="json"),
                                     hydrology={"enabled": False})
        self.inputs = LandcoverInputs(self.topology, self.facts_at, {})
        self.ctx = LightGridBakeContext(self.world, [], LocationsIndexWire(),
                                        [(0, 0), (0, 1), (1, 0), (1, 1)], self.scale)

    @staticmethod
    def facts_at(coord):
        return RegionFacts(climate=ClimateFacts(rainfall_mean=65 if coord[0] < 8 else 15))

    def declare(self, *specs):
        self.world.terrain_masks = WorldTerrainMasks(default_landcover=self.policy,
                                                     declared_regions=list(specs)).model_dump(mode="json")

    def plugin(self, **changes):
        return LandcoverMaterializer(replace(self.inputs, **changes))

    def no_auto(self):
        self.policy = self.policy.model_copy(update={"autoresolve": False})

    def paint(self, plugin, ctx=None):
        ctx = ctx or self.ctx
        compose = LightGridCompose(self.scale)
        run_mask_domain(compose, ctx, plugin)
        return {(gx, gy, tx, ty): cell.system_terrain for gx, gy in ctx.tiles
                for tx, ty, cell in compose.iter_tile(gx, gy)}

    def test_partial_and_full_bake_identical_for_all_topologies(self):
        for mode in WorldTopologyMode:
            with self.subTest(mode=mode):
                topology = WorldTopology(mode=mode, bounds=self.topology.bounds)
                full_plugin = self.plugin(topology=topology)
                full = self.paint(full_plugin)
                partial = self.paint(self.plugin(topology=topology), replace(self.ctx, tiles=[(1, 0)]))
                self.assertEqual(partial, {key: value for key, value in full.items() if key[:2] == (1, 0)})
                self.assertTrue(full)
                self.assertIn(self.forest, full.values())
                self.assertIn(self.plains, full.values())
                all_regions = full_plugin.collect(self.ctx, self.policy)
                partial_regions = self.plugin(topology=topology).collect(replace(self.ctx, tiles=[(1, 0)]), self.policy)
                self.assertEqual([r.region_uid for r in all_regions], [r.region_uid for r in partial_regions])

    def test_declared_arid_forest_warns_and_paints_but_auto_is_not_forest(self):
        self.no_auto()
        shape = BboxShape(x_min=8, y_min=0, x_max=15, y_max=15)
        self.declare(ForestSpec(name="arid forest", shape=shape))
        plugin = self.plugin()
        with self.assertLogs(level="WARNING") as logs:
            painted = self.paint(plugin)
        self.assertIn("declared_without_suitability", " ".join(logs.output))
        self.assertEqual(set(painted.values()), {self.forest})
        auto = plugin.autoresolve_specs(self.ctx, self.policy)
        self.assertTrue(auto)
        for region in auto:
            if region.current_type == self.forest:
                self.assertTrue(all(sub.seed_xy[0] < 8 for sub in region.sublocations))

    def test_anchor_is_resolved_in_collect_and_keeps_anchor_identity(self):
        self.no_auto()
        self.declare()
        spec = ForestSpec(name="anchor woods", shape=AnchorRadiusShape(anchor_uid="named-anchor", radius=4))
        self.ctx.locations = [SimpleNamespace(location_uid="named-anchor", map_x=4, map_y=4)]
        plugin = self.plugin(anchor_specs=(AnchoredRegion("named-anchor", spec),))
        region = plugin.collect(self.ctx, self.policy)[0]
        self.assertEqual(region.region_uid, region_uid(self.world.world_uid, anchor_uid="named-anchor"))
        self.assertEqual(region.source, RegionSource.ANCHOR)
        self.assertEqual((region.spec.shape.cx, region.spec.shape.cy), (4, 4))
        footprint = plugin.materialize(region, self.scale)
        self.ctx.locations.clear()  # Materialize does not re-read anchors/world.
        self.assertEqual(plugin.materialize(region, self.scale), footprint)

    def test_missing_anchor_is_unresolved_without_origin_default(self):
        self.no_auto()
        self.declare(ForestSpec(name="missing", shape=AnchorRadiusShape(anchor_uid="absent", radius=4)))
        with self.assertLogs(level="WARNING") as logs:
            self.assertEqual(self.plugin().collect(self.ctx, self.policy), [])
        self.assertIn("reason=missing_anchor", " ".join(logs.output))

    def test_source_merge_prefers_declaration_to_matching_anchor(self):
        self.no_auto()
        shape = BboxShape(x_min=0, y_min=0, x_max=7, y_max=7)
        declared = PlainSpec(name="same", shape=shape)
        anchor = ForestSpec(name="same", shape=shape)
        self.declare(declared)
        regions = self.plugin(anchor_specs=(AnchoredRegion("anchor", anchor),)).collect(self.ctx, self.policy)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].source, RegionSource.DECLARED)

    def test_snapshot_preserves_current_type_tombstone_and_unknown_key(self):
        self.no_auto()
        self.declare(ForestSpec(name="forest", shape=BboxShape(x_min=0, y_min=0, x_max=7, y_max=7)))
        uid = region_uid(self.world.world_uid, name="forest")
        snapshot = {uid: StateSnapshotEntry(self.plains)}
        painted = self.paint(self.plugin(state_snapshot=snapshot))
        self.assertEqual(set(painted.values()), {self.plains})
        self.assertEqual(snapshot[uid].current_type, self.plains)
        self.assertEqual(self.paint(self.plugin(state_snapshot={uid: StateSnapshotEntry(self.plains, True)})), {})
        with self.assertLogs(level="WARNING"):
            self.assertEqual(self.paint(self.plugin(state_snapshot={uid: StateSnapshotEntry("unknown")})), {})

    def test_overlap_uses_common_precedence_independent_of_apply_order(self):
        self.no_auto()
        a = PlainSpec(name="broad", shape=BboxShape(x_min=0, y_min=0, x_max=15, y_max=15), placement_specificity=1)
        b = PlainSpec(name="specific", shape=BboxShape(x_min=0, y_min=0, x_max=7, y_max=7), placement_specificity=2)
        self.declare(a, b)
        results = []
        for order in permutations(self.plugin().collect(self.ctx, self.policy)):
            plugin, compose = self.plugin(), LightGridCompose(self.scale)
            for region in order:
                plugin.apply(compose, plugin.materialize(region, self.scale), region,
                             WorldTerrainMasks(), tile_set=set(self.ctx.tiles), ctx=self.ctx)
            results.append({ref: value.region_uid for ref, value in plugin.winners.items()})
        self.assertEqual(results[0], results[1])
        self.assertIn(region_uid(self.world.world_uid, name="specific"), results[0].values())

    def test_apply_preserves_hydro_and_higher_rank_terrain(self):
        self.no_auto()
        self.declare(PlainSpec(name="plains", shape=BboxShape(x_min=0, y_min=0, x_max=7, y_max=7)))
        plugin, compose = self.plugin(), LightGridCompose(self.scale)
        compose.ensure(0, 0, 0, 0).hydrology_role = WorldMapHydrologyRole.LAKE
        road = WorldTerrainMasks().default_roads.system_terrain
        compose.ensure(0, 0, 1, 0).system_terrain = road
        region = plugin.collect(self.ctx, self.policy)[0]
        plugin.apply(compose, plugin.materialize(region, self.scale), region,
                     WorldTerrainMasks(), tile_set={(0, 0)}, ctx=self.ctx)
        self.assertIsNone(compose.get(0, 0, 0, 0).system_terrain)
        self.assertEqual(compose.get(0, 0, 1, 0).system_terrain, road)

    def test_seed_determinism_negative_coordinates_and_required_policy(self):
        topology = WorldTopology(mode=WorldTopologyMode.WRAPPED,
                                  bounds=WorldBounds(x_min=-8, y_min=-8, x_max=7, y_max=7))
        seeds = generate_seeds(self.world.world_uid, topology, self.policy)
        self.assertEqual(seeds, generate_seeds(self.world.world_uid, topology, self.policy))
        self.assertEqual(len(seeds), 16)
        self.assertEqual(len({seed.coord for seed in seeds}), len(seeds))
        self.assertTrue(all(topology.bounds.contains(*seed.coord) for seed in seeds))
        with self.assertRaises(ValidationError):
            LandcoverRegionsCategoryPolicy()
        self.assertEqual(self.plugin().category_policy(WorldTerrainMasks()),
                         LandcoverRegionsCategoryPolicy.canonical_defaults())

    def test_merge_canonical_owner_sublocation_uids_facings_and_seam(self):
        topology = WorldTopology(mode=WorldTopologyMode.WRAPPED,
                                  bounds=WorldBounds(x_min=0, y_min=0, x_max=15, y_max=3))
        seeds = (CoverageSeed(WorldSeed((0, 1), (0, 0)), self.forest),
                 CoverageSeed(WorldSeed((15, 1), (3, 0)), self.forest))
        for order in permutations(seeds):
            regions = merge_sublocations(order, topology, self.policy, self.world.world_uid)
            self.assertEqual(len(regions), 1)
            region = regions[0]
            self.assertEqual(region.region_uid, region_uid(self.world.world_uid, region_seed_xy=(0, 1)))
            self.assertEqual(len(region.sublocations), 2)
            self.assertTrue(all(sub.facing is not None for sub in region.sublocations))
            for sub in region.sublocations:
                self.assertEqual(sub.region_uid, region_uid(self.world.world_uid, seed_xy=sub.seed_xy))
                self.assertIsNone(sub.placement_specificity)

    def test_declared_edge_noise_and_claim_noise_change_actual_contours(self):
        self.no_auto()
        shape = BboxShape(x_min=0, y_min=0, x_max=15, y_max=15, edge_noise=EdgeNoise(amplitude=4, scale=3))
        self.declare(ForestSpec(name="organic", shape=shape))
        plugin = self.plugin(facts_at=lambda _: RegionFacts(climate=ClimateFacts(rainfall_mean=70)))
        region = plugin.collect(self.ctx, self.policy)[0]
        context = RegionRasterContext(region.region_uid, region.spec, self.scale, region.topology)
        noisy = rasterize_fine(region.spec.shape, region, context)
        smooth = rasterize_fine(shape.model_copy(update={"edge_noise": None}), region, context)
        self.assertTrue(noisy)
        self.assertLess(len(noisy), len(smooth))
        auto = self.plugin().autoresolve_specs(self.ctx, self.policy)
        changed = False
        for region in auto:
            context = RegionRasterContext(region.region_uid, region.spec, self.scale, region.topology)
            noisy = rasterize_claim_fine(region.claim, region, context)
            claim = replace(region.claim, noise=EdgeNoise(amplitude=0, scale=3))
            changed |= noisy != rasterize_claim_fine(claim, region, context)
        self.assertTrue(changed)

    def test_hydrology_is_only_indexed_without_guessed_ownership(self):
        hydro = WorldHydrology(declared_lakes=[{"location_uid": "lake", "shoreline": []}])
        cell = MapCellHydrology(role=HydrologyCellRole.LAKE)
        surface = SimpleNamespace(coarse_hydro={(0, 0): cell})
        result = index_hydrology(self.world.world_uid, hydro, surface)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].status, HydroIndexStatus.DECLARED)
        self.assertEqual(result[0].location_uid, "lake")
        self.assertEqual(result[1].status, HydroIndexStatus.OBSERVED)
        self.assertIsNone(result[1].region_uid)
        self.assertEqual(surface.coarse_hydro, {(0, 0): cell})
        self.assertEqual(len(hydro.declared_lakes), 1)

    def test_flora_rule_vetoes_autoresolve_but_not_declared_forest(self):
        rule = EligibilityRule(fact="flora.eligible_trees", op=EligibilityOp.FLAG, required=True)
        entries = [entry.model_copy(update={"eligibility": [*entry.eligibility, rule]})
                   if entry.system_terrain == self.forest else entry for entry in self.registry.root]
        self.world.terrain_registry = WorldTerrainRegistry(entries).model_dump(mode="json")
        auto = self.plugin().autoresolve_specs(self.ctx, self.policy)
        self.assertTrue(auto)
        self.assertTrue(all(region.current_type != self.forest for region in auto))
        self.no_auto()
        self.declare(ForestSpec(name="authored", shape=BboxShape(x_min=0, y_min=0, x_max=7, y_max=7)))
        with self.assertLogs(level="WARNING") as logs:
            self.assertEqual(set(self.paint(self.plugin()).values()), {self.forest})
        self.assertIn("declared_without_suitability", " ".join(logs.output))

    def test_merge_respects_kind_radius_and_reflected_sphere_neighbor(self):
        topology = WorldTopology(mode=WorldTopologyMode.SPHERE,
                                  bounds=WorldBounds(x_min=0, y_min=0, x_max=15, y_max=7))
        seeds = (CoverageSeed(WorldSeed((1, 7), (0, 1)), self.forest),
                 CoverageSeed(WorldSeed((9, 7), (2, 1)), self.forest))
        self.assertEqual(len(merge_sublocations(seeds, topology, self.policy, self.world.world_uid)), 1)
        different = (seeds[0], replace(seeds[1], target_key=self.plains))
        self.assertEqual(len(merge_sublocations(different, topology, self.policy, self.world.world_uid)), 2)
        planar = WorldTopology(mode=WorldTopologyMode.PLANAR, bounds=topology.bounds)
        self.assertEqual(len(merge_sublocations(seeds, planar, self.policy, self.world.world_uid)), 2)

    def test_claim_area_is_full_field_area_before_light_sampling(self):
        plugin = self.plugin()
        for region in plugin.autoresolve_specs(self.ctx, self.policy):
            context = RegionRasterContext(region.region_uid, region.spec, self.scale, region.topology)
            self.assertEqual(region.claim_area, len(rasterize_claim_fine(region.claim, region, context)))
            self.assertLess(region.claim_area, region.spec.shape.area())


if __name__ == "__main__":
    unittest.main()
