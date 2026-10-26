"""Wilderness-6 L0 acceptance through the contributor and shared writer."""

from dataclasses import replace
from itertools import permutations
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.application.worldData.generators.climate.climateAnchor import ClimateAnchorPoint, AnchorSource
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry
from app.application.worldData.masks.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.landcover import LandcoverContributor
from app.application.worldData.pack.bake.lightGrid.contributors.landcoverInputs import prepare_landcover_inputs
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.lightGrid.maskDomainRegistry import contributor_for_mask_domain
from app.application.worldData.pack.bake.lightGrid.paintTerrain import paint_system_terrain_cell
from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.masks.enums.maskDomainId import LightContributorId, MaskDomainId
from app.dataModel.spatial.regionShape import BboxShape, EdgeNoise
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.dataModel.terrainMasks.regions import ForestSpec, PlainSpec, FarmlandSpec
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.wire.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexWire
from app.dataModel.worldPack.wire.worldMapCellWire import WorldMapCellWire
from app.ids.regionIdentity import region_uid


class LandcoverContributorTests(unittest.TestCase):
    def setUp(self):
        self.registry = WorldTerrainRegistry.canonical_defaults()
        self.policy = LandcoverRegionsCategoryPolicy(
            autoresolve=False, seed_spacing=8, max_radius=10,
            claim_noise=EdgeNoise(amplitude=3, scale=4),
        )
        self.world = SimpleNamespace(
            world_uid="wilderness-6-smoke", world_topology_mode="planar",
            world_bounds={"x_min": 0, "y_min": 0, "x_max": 1, "y_max": 0},
            terrain_registry=self.registry.model_dump(mode="json"), hydrology={"enabled": False},
        )
        # Registry wire is an array; world rainfall override exercises caller profile resolution.
        self.world.climate_zone_registry = [
            {**ClimateZone.TEMPERATE.to_entry().model_dump(mode="json"), "base_rainfall": 80},
        ]
        surface = SimpleNamespace(
            local_field=ClimateAnchorField((ClimateAnchorPoint(
                0, 0, ClimateZone.TEMPERATE.system_climate, None, AnchorSource.AUTO),)),
            coarse_hydro={}, coarse_surface_z={(0, 0): 0, (1, 0): 0},
            coarse_relief_z={(0, 0): 0, (1, 0): 0},
        )
        self.ctx = LightGridBakeContext(
            self.world, [], LocationsIndexWire(), [(0, 0), (1, 0)],
            LightGridScale.from_tile(32, 32), surface_planning=surface,
            terrain_system_keys={entry.system_terrain for entry in self.registry.root},
        )
        self.declare()

    def declare(self, *specs):
        self.world.terrain_masks = WorldTerrainMasks(
            default_landcover=self.policy, declared_regions=list(specs),
        ).model_dump(mode="json")

    def bake(self, ctx=None, compose=None):
        ctx = ctx or self.ctx
        compose = compose or LightGridCompose(ctx.scale)
        for tile in ctx.tiles:
            compose.ensure_tile(*tile)
        LandcoverContributor().apply(compose, ctx)
        return {(gx, gy): compose.to_wire_tile(gx, gy) for gx, gy in ctx.tiles}

    def test_smoke_forest_plains_farmland_organic_density_background_and_wire(self):
        specs = [kind(name=kind.__name__, shape=BboxShape(
            x_min=x, y_min=5, x_max=x + 12, y_max=25,
            edge_noise=EdgeNoise(amplitude=4, scale=3)), density=0.75)
                 for kind, x in ((ForestSpec, 3), (PlainSpec, 23), (FarmlandSpec, 43))]
        self.declare(*specs)
        with self.assertLogs(level="DEBUG") as logs:
            full = self.bake()
        output = " ".join(logs.output)
        self.assertIn("source=spec", output)
        self.assertIn("source=fallback", output)
        all_cells = [c for cells in full.values() for c in cells]
        for spec in specs:
            uid = region_uid(self.world.world_uid, name=spec.name)
            members = [c for c in all_cells if c.region_uid == uid]
            self.assertTrue(members)
            self.assertEqual({c.system_terrain for c in members}, {spec.entry_type})
            self.assertLess(len(members), spec.shape.area())
        self.assertTrue(any(c.region_uid is None and c.system_terrain is not None for c in all_cells))
        self.assertEqual(full[(1, 0)], self.bake(replace(self.ctx, tiles=[(1, 0)]))[(1, 0)])
        for cell in all_cells:
            self.assertEqual(WorldMapCellWire.model_validate_json(cell.model_dump_json()), cell)
        self.assertIsNone(WorldMapCellWire(tx=0, ty=0).region_uid)
        with tempfile.TemporaryDirectory() as tmp:
            paths = WorldPackPaths.from_db_parent(str(Path(tmp) / "smoke.db"), self.world.world_uid)
            writer = WorldPackWriter(paths)
            writer.sync_world_metadata(
                SimpleNamespace(fine_cells_per_map_cell=32, world_map_cells_per_tile=None),
                cells_per_side=32,
            )
            for tile, cells in full.items():
                writer.write_world_map_tile(*tile, cells, cells_per_side=32)
            writer.save_manifest()
            reader = WorldPackReader(paths)
            for tile, cells in full.items():
                side, loaded = reader.read_world_map_tile(*tile)
                self.assertEqual(side, 32)
                self.assertEqual(loaded, cells)

    def test_background_does_not_override_lower_rank_region(self):
        self.declare(PlainSpec(name="plain", shape=BboxShape(x_min=0, y_min=0, x_max=31, y_max=31)))
        compose = LightGridCompose(self.ctx.scale)
        compose.ensure_tile(0, 0)
        for _, _, cell in compose.iter_tile(0, 0):
            cell.climate_zone_id = ClimateZone.TEMPERATE.world_map_wire_id()
        cells = self.bake(compose=compose)[(0, 0)]
        self.assertEqual({c.system_terrain for c in cells}, {self.registry.plains_terrain_key()})
        self.assertTrue(all(c.region_uid for c in cells))

    def test_state_read_boundary_uses_custom_terrain_and_logs_source(self):
        spec = ForestSpec(name="changed", shape=BboxShape(x_min=0, y_min=0, x_max=31, y_max=31))
        self.declare(spec)
        uid = region_uid(self.world.world_uid, name=spec.name)
        custom = self.registry.root[0].model_copy(update={"system_terrain": "steppe", "merge_rank": 1})
        self.world.terrain_registry = WorldTerrainRegistry([*self.registry.root, custom]).model_dump(mode="json")
        with patch("app.application.worldData.pack.bake.lightGrid.contributors.landcoverInputs.read_region_state_snapshot",
                   return_value={uid: StateSnapshotEntry("steppe")}), self.assertLogs(level="DEBUG") as logs:
            cells = self.bake()[(0, 0)]
        self.assertEqual({c.system_terrain for c in cells}, {"steppe"})
        self.assertEqual({c.region_uid for c in cells}, {uid})
        self.assertIn("source=state", " ".join(logs.output))

    def test_equal_rank_order_independent_winner_uid_and_warning(self):
        forest_rank = self.registry.entry_for(self.registry.forest_terrain_key()).merge_rank
        self.world.terrain_registry = WorldTerrainRegistry([
            entry.model_copy(update={"merge_rank": forest_rank}) for entry in self.registry.root
        ]).model_dump(mode="json")
        shape = BboxShape(x_min=0, y_min=0, x_max=2, y_max=2)
        specs = (ForestSpec(name="forest", shape=shape),
                 PlainSpec(name="specific", shape=shape, placement_specificity=0))
        results = []
        for ordered in permutations(specs):
            self.declare(*ordered)
            with self.assertLogs(level="WARNING") as logs:
                results.append(self.bake())
            self.assertIn("equal_rank_resolved", " ".join(logs.output))
        self.assertEqual(*results)
        self.assertEqual(results[0][(0, 0)][0].region_uid,
                         region_uid(self.world.world_uid, name="specific"))

    def test_hydro_preserved_and_structural_repaint_clears_uid(self):
        self.declare(ForestSpec(name="woods", shape=BboxShape(x_min=0, y_min=0, x_max=31, y_max=31)))
        compose = LightGridCompose(self.ctx.scale)
        roles = (WorldMapHydrologyRole.SEA, WorldMapHydrologyRole.LAKE, WorldMapHydrologyRole.RIVER)
        for tx, role in enumerate(roles):
            cell = compose.ensure(0, 0, tx, 0)
            cell.hydrology_role, cell.system_terrain = role, self.registry.plains_terrain_key()
        self.bake(compose=compose)
        for tx, role in enumerate(roles):
            cell = compose.get(0, 0, tx, 0)
            self.assertEqual(cell.hydrology_role, role)
            self.assertEqual(cell.system_terrain, self.registry.plains_terrain_key())
            self.assertIsNone(cell.region_uid)
        cell = compose.get(0, 0, 4, 0)
        self.assertIsNotNone(cell.region_uid)
        snap = cell.seam_copy()
        other = compose.ensure(1, 0, 4, 0)
        other.apply_seam_copy(snap)
        self.assertEqual(other.region_uid, cell.region_uid)
        road = WorldTerrainMasks().default_roads.system_terrain
        paint_system_terrain_cell(compose, 0, 0, 4, 0, road, registry=self.registry)
        self.assertIsNone(cell.region_uid)
        apply_terrain_footprint(compose, MaskFootprint(frozenset({LightCellRef(1, 0, 4, 0)})),
                                system_terrain=road, registry=self.registry)
        self.assertIsNone(other.region_uid)

    def test_input_facts_use_world_profile_and_global_bounds(self):
        full = prepare_landcover_inputs(self.ctx)
        partial = prepare_landcover_inputs(replace(self.ctx, tiles=[(1, 0)]))
        self.assertEqual(full.topology, partial.topology)
        self.assertEqual(full.facts_at((40, 10)), partial.facts_at((40, 10)))
        self.assertEqual(full.facts_at((40, 10)).climate.rainfall_mean, 80)
        self.assertEqual(contributor_for_mask_domain(MaskDomainId.LANDCOVER), LightContributorId.LANDCOVER)

    def test_autoresolve_through_contributor_is_scope_independent(self):
        self.policy = self.policy.model_copy(update={"autoresolve": True, "seed_spacing": 4, "max_radius": 5})
        self.ctx.scale = LightGridScale.from_tile(8, 8)
        self.declare()
        full = self.bake()
        self.assertTrue(any(c.region_uid for cells in full.values() for c in cells))
        partial = self.bake(replace(self.ctx, tiles=[(1, 0)]))
        self.assertEqual(full[(1, 0)], partial[(1, 0)])

    def test_disabled_landcover_policy_disables_regions_and_background(self):
        self.policy = self.policy.model_copy(update={"enabled": False})
        self.declare(ForestSpec(name="off", shape=BboxShape(x_min=0, y_min=0, x_max=31, y_max=31)))
        cells = self.bake()[(0, 0)]
        self.assertTrue(all(c.region_uid is None and c.system_terrain is None for c in cells))


if __name__ == "__main__":
    unittest.main()
