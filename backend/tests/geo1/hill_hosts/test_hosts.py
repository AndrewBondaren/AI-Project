from copy import replace
from unittest import TestCase

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.hills.hillPlacement import place_hills
from app.application.worldData.generators.terrain.landcover.planning.capturedSources import capture_landcover_policy
from app.application.worldData.generators.terrain.landcover.planning.preWaterHillHosts import PreWaterHillHostPlanner, PreWaterHillHostJob
from app.application.worldData.generators.terrain.relief.surfaceCoating.sources import SupportSources
from app.application.worldData.masks.regionIdentity import declared_region_identity
from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND
from app.dataModel.climate.enums.climateZone import ClimateZoneProfileData
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ResolvedClimateProfile
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.regions.regionState import RegionState
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.regionShape import BboxShape, AnchorRadiusShape
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage, CoverageSpan
from app.dataModel.terrainMasks.regions import PlainSpec
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverTerrainPolicy
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from tests.geo1.coating.fixtures import envelope, prepared
from tests.geo1.support_sources.fixtures import captured


def bases():
    climate = envelope("climate_base", ClimateBasePlan(poles=(), bbox=None, default_zone="temperate",
        profiles=(ResolvedClimateProfile(key="temperate", values=ClimateZoneProfileData(15, 0, 50, 10, 10)),),
        blend=CLIMATE_POLE_BLEND))
    terrain = envelope("terrain_base", TerrainPlan(bbox=GridBBox(x_min=0, y_min=0, x_max=1, y_max=1),
        surface_z=tuple((SurfaceGridCoord(x, y), 0) for y in range(2) for x in range(2))),
        (PlanDependency(slot="climate_base", ref=climate.ref),))
    return climate, terrain


def coverage(x0=0, x1=4, y0=0, y1=4):
    return RegionCoverage(region_uid="world", spans=tuple(CoverageSpan(y=y, x0=x0, x1=x1) for y in range(y0, y1)))


class PreWaterHillHostsTests(TestCase):
    def project(self, inputs, cells=None, base=None):
        return PreWaterHillHostPlanner().prepare("world", inputs, *(base or bases()), cells=cells or coverage())

    def test_captured_policy_drives_real_hills_without_final_water_inputs(self):
        inputs = captured(grid=SurfaceGridSettings(fine_span=16, light_side=2))
        policy = HillPolicy(min_spacing=6, radius=2, height=3, shapes=("circle",))
        inputs = replace(inputs, terrain_entries=tuple(replace(e, hills=policy) for e in inputs.terrain_entries))
        hosts = self.project(inputs, coverage(0, 32, 0, 32))
        z = {xy: 0 for xy, _ in hosts}
        registry, _ = capture_landcover_policy(inputs)
        place_hills(z, dict(hosts), frozenset(), terrain_registry=registry, seed=inputs.seed, z_min=0, z_max=20)
        self.assertEqual(len(z), 1024)
        self.assertEqual(max(z.values()), 3)
        self.assertTrue(any(v == 0 for v in z.values()))

    def test_partial_requests_replay_same_declared_state_projection(self):
        spec = PlainSpec(name="patch", shape=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1))
        inputs = captured(masks=WorldTerrainMasks(declared_regions=(spec,)))
        state = RegionState(region_uid=declared_region_identity("world", spec).region_uid, current_type="farmland")
        inputs = replace(inputs, region_states=(state,))
        full = dict(self.project(inputs))
        parts = dict(self.project(inputs, coverage(2, 4)) + self.project(inputs, coverage(0, 2)))
        self.assertEqual(full, parts)
        self.assertEqual(full[(0, 0)], "farmland")
        tombstone = replace(inputs, region_states=(replace(state, tombstone=True),))
        self.assertNotEqual(dict(self.project(tombstone))[(0, 0)], "farmland")

    def test_pre_water_and_coating_share_captured_selection_and_presence(self):
        inputs = captured()
        override = LandcoverTerrainPolicy(system_terrain="forest", hills=None)
        inputs = replace(inputs, terrain_entries=tuple(replace(e, hills_authored=False) if e.key == "forest" else e
            for e in inputs.terrain_entries), landcover=replace(inputs.landcover, terrain_policies=(override,),
            terrain_policy_hills_authored=("forest",)))
        _, deps = prepared(inputs)
        post = SupportSources("world", inputs, deps.climate_base.payload, deps.climate_local.payload,
                              deps.terrain_base.payload, deps.hydrology.payload)
        self.assertEqual(dict(self.project(inputs)), {xy: post.terrain_at(xy) for xy, _ in self.project(inputs)})
        registry, _ = capture_landcover_policy(inputs)
        self.assertIsNone(registry.entry_for("forest").hills)
        self.assertEqual(registry, post.registry)
        decoded = type(inputs).model_validate_json(inputs.model_dump_json())
        self.assertEqual(self.project(inputs), self.project(decoded))
        self.assertEqual(capture_landcover_policy(decoded)[0], registry)

    def test_required_hydrology_is_unknown_and_cannot_admit_autoresolved_region(self):
        inputs = captured()
        rule = EligibilityRule(fact="hydrology.open_water_fraction", op="lte", hi=0, required=True)
        inputs = replace(inputs, terrain_entries=tuple(replace(e, eligibility=(rule,)) for e in inputs.terrain_entries),
                         landcover=replace(inputs.landcover, autoresolve=True, seed_spacing=1))
        job = PreWaterHillHostJob("world", inputs, *bases())
        facts = job.facts_at((0, 0))
        self.assertIsNone(facts.hydrology)
        self.assertIsNone(facts.value_for(rule.fact))
        self.assertIsNotNone(facts.climate)
        self.assertEqual(facts.relief.elevation_mean, 0)
        self.assertEqual(job.sources.regions, [])

    def test_missing_anchor_does_not_invent_host_terrain(self):
        spec = PlainSpec(name="anchor", shape=AnchorRadiusShape(anchor_uid="missing", radius=1))
        inputs = captured(masks=WorldTerrainMasks(declared_regions=(spec,)))
        with self.assertRaises(PlanBuildFailure):
            self.project(inputs)

    def test_disabled_masks_have_no_landcover_hosts(self):
        self.assertEqual(self.project(replace(captured(), masks_enabled=False)), ())

    def test_wrong_revision_world_extent_and_noncanonical_scope_rejected(self):
        inputs = captured()
        climate, terrain = bases()
        with self.assertRaisesRegex(ValueError, "bind"):
            self.project(inputs, base=(climate, replace(terrain, dependencies=())))
        foreign = replace(climate, ref=replace(climate.ref, key=replace(climate.ref.key, world_uid="other")))
        with self.assertRaisesRegex(ValueError, "same-world"):
            self.project(inputs, base=(foreign, terrain))
        changed = envelope("terrain_base", TerrainPlan(bbox=GridBBox(x_min=0, y_min=0, x_max=0, y_max=0),
                           surface_z=((SurfaceGridCoord(0, 0), 0),)),
                           terrain.dependencies)
        with self.assertRaisesRegex(ValueError, "extent"):
            self.project(inputs, base=(climate, changed))
        with self.assertRaisesRegex(ValueError, "canonical"):
            self.project(inputs, coverage(-1, 1))
