"""Step 8: independent identities, snapshot index, atomic publication and debug HTTP."""
from tests.planning.consumers.test_wiring import working_fixture
from tests.planning.consumers.test_l0_l2 import frozen_surface_fixture
from dataclasses import fields, replace
from itertools import permutations
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
from app.application.cancellation.requestPlanWait import RequestPlanWait

from app.api.deps import get_container
from app.api.routes.map import router
from app.application.worldData.generators.terrain.landcover.types import AnchoredRegion, Sublocation, StateSnapshotEntry
from app.application.worldData.generators.terrain.landcover.regionIdentityCheck import require_unique_region_uids
from app.application.worldData.pack.bake.l0.wildernessRegionIndex import build_region_index
from app.application.worldData.pack.bake.l0.worldMapBakeOrchestrator import WorldMapBakeOrchestrator
from app.application.worldData.pack.io.packManifestStore import PackManifestStore
from app.application.worldData.pack.io.wildernessRegionIndexWriter import replace_region_index
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.pack.read.wildernessRegionReadService import WildernessRegionReadService
from app.application.worldData.render.regions.regionOutline import render_region_outline
from app.dataModel.spatial.regionShape import BboxShape, AnchorRadiusShape
from app.dataModel.terrainMasks.regions import ForestSpec, PlainSpec
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionStatus
from app.dataModel.worldPack.wire.worldMapCellWire import WorldMapCellWire
from app.ids import region_uid, state_fingerprint
from app.db.models.world import World
from tests import test_landcover_materializer as source_fixture
from tests import test_landcover_contributor as bake_fixture


class WildernessRegionIndexTests(unittest.TestCase):
    def setUp(self):
        self.f = source_fixture.LandcoverMaterializerTests()
        self.f.setUp()
        from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
        self.f.registry.root.append(TerrainRegistryEntry(system_terrain="steppe", terrain_category="solid"))
        self.f.world.terrain_registry = self.f.registry.model_dump(mode="json")

    def regions(self):
        self.f.declare(ForestSpec(name="declared", shape=BboxShape(x_min=1,y_min=1,x_max=4,y_max=4)))
        spec = PlainSpec(name="anchored",shape=AnchorRadiusShape(anchor_uid="anchor",radius=2))
        self.f.ctx = replace(self.f.ctx, locations=(SimpleNamespace(location_uid="anchor",map_x=10,map_y=10),))
        plugin = self.f.plugin(anchor_specs=(AnchoredRegion("anchor",spec),))
        return plugin.collect(self.f.ctx,self.f.policy)

    def test_uid_sources_are_disjoint_and_existing_seed_ids_survive(self):
        for seed in ((0,0),(-1,2),(15,1)):
            parent = region_uid("w",region_seed_xy=seed)
            child = region_uid("w",seed_xy=seed)
            self.assertNotEqual(parent,child)
            self.assertEqual(parent,region_uid("w",region_seed_xy=seed))
        with self.assertRaises(ValueError):
            region_uid("w",region_seed_xy=(0,0),seed_xy=(0,0))

    def test_all_statuses_parent_links_snapshot_types_and_determinism(self):
        regions = self.regions()
        entries = build_region_index(regions,self.f.scale, registry=self.f.registry)
        self.assertEqual({e.status for e in entries},set(WildernessRegionStatus))
        self.assertEqual(len(entries),len({e.region_uid for e in entries}))
        parents = {e.region_uid:e for e in entries if e.parent_region_uid is None}
        for e in entries:
            if e.parent_region_uid is not None:
                self.assertIn(e.parent_region_uid,parents)
                self.assertNotEqual(e.parent_region_uid,e.region_uid)
        self.assertEqual(entries,build_region_index(list(reversed(regions)),self.f.scale, registry=self.f.registry))
        partial = self.f.plugin().collect(replace(self.f.ctx,tiles=[(0,0)]),self.f.policy)
        full = self.f.plugin().collect(self.f.ctx,self.f.policy)
        self.assertEqual(build_region_index(partial,self.f.scale, registry=self.f.registry),build_region_index(full,self.f.scale, registry=self.f.registry))
        declared = next(r for r in regions if r.spec.name == "declared")
        changed = replace(declared,current_type="steppe")
        entry = build_region_index([changed],self.f.scale, registry=self.f.registry)[0]
        self.assertEqual((entry.entry_type,entry.current_type),("forest","steppe"))
        self.assertEqual(entry.spec_fingerprint,state_fingerprint(changed.spec.model_dump(mode="json")))
        self.assertNotEqual(entry.spec_fingerprint,build_region_index([
            replace(changed,spec=changed.spec.model_copy(update={"density":0.5}))],self.f.scale, registry=self.f.registry)[0].spec_fingerprint)

    def test_collisions_and_self_parent_are_rejected_before_publication(self):
        regions = self.regions()
        root = regions[0]
        for bad in ([root,root], [replace(root,sublocations=(Sublocation((0,0),root.region_uid,None),))]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                require_unique_region_uids(bad)
        entries = build_region_index(regions,self.f.scale, registry=self.f.registry)
        manifest = WorldPackManifest(world_uid=self.f.world.world_uid,wilderness_region_entries=entries)
        before = manifest.model_dump_json()
        with self.assertRaises(ValueError):
            replace_region_index(manifest,[entries[0],entries[0]])
        self.assertEqual(manifest.model_dump_json(),before)
        child = next(e for e in entries if e.parent_region_uid is not None)
        for bad in ([child], [child.model_copy(update={"parent_region_uid":child.region_uid})]):
            with self.assertRaises(ValueError):
                replace_region_index(manifest,bad)
        with self.assertRaises(ValidationError):
            WorldPackManifest(world_uid="w",wilderness_region_entries=[entries[0],entries[0]])

    def test_collect_rejects_distinct_declarations_with_colliding_ids(self):
        self.f.no_auto()
        self.f.declare(ForestSpec(name="one",shape=BboxShape(x_min=0,y_min=0,x_max=3,y_max=3)),
                       ForestSpec(name="two",shape=BboxShape(x_min=4,y_min=0,x_max=7,y_max=3)))
        with patch("app.application.worldData.generators.terrain.landcover.materializer.declared_region_identity",
                   return_value=SimpleNamespace(region_uid="forced-collision")):
            with self.assertRaisesRegex(ValueError,"duplicate"):
                self.f.plugin().collect(self.f.ctx,self.f.policy)

    def test_autoresolve_collision_is_not_hidden_by_source_merge(self):
        regions = self.f.plugin().autoresolve_specs(self.f.ctx,self.f.policy)
        self.assertGreaterEqual(len(regions),2)
        collided = [regions[0],replace(regions[1],region_uid=regions[0].region_uid)]
        plugin = self.f.plugin()
        with patch.object(plugin,"autoresolve_specs",return_value=collided):
            with self.assertRaisesRegex(ValueError,"duplicate"):
                plugin.collect(self.f.ctx,self.f.policy)

    def test_seed_parts_keep_identity_across_merge_and_split(self):
        from app.application.worldData.generators.terrain.landcover.autoresolve.mergeSublocations import CoverageSeed, merge_sublocations
        from app.application.worldData.generators.terrain.landcover.autoresolve.seedGrid import WorldSeed
        a = CoverageSeed(WorldSeed((1,1),(0,0)),"forest")
        b = CoverageSeed(WorldSeed((5,1),(1,0)),"forest")
        from app.application.worldData.generators.terrain.landcover.autoresolve.claim import fine_topology
        topology = fine_topology(self.f.topology,self.f.scale.tile_macro)
        merged = merge_sublocations((a,b),topology,self.f.policy,"w")
        split = merge_sublocations((a,replace(b,target_key="plains")),topology,self.f.policy,"w")
        self.assertEqual(len(merged),1)
        self.assertEqual(len(split),2)
        self.assertEqual({s.region_uid for r in merged for s in r.sublocations},
                         {s.region_uid for r in split for s in r.sublocations})
        for components in (merged,split):
            uids = [uid for r in components for uid in (r.region_uid,*(s.region_uid for s in r.sublocations))]
            self.assertEqual(len(uids),len(set(uids)))

    def test_manifest_round_trip_replacement_and_atomic_collision_rejection(self):
        entries = build_region_index(self.regions(),self.f.scale, registry=self.f.registry)
        with tempfile.TemporaryDirectory() as tmp:
            paths = WorldPackPaths.from_db_parent(str(Path(tmp)/"game.db"),self.f.world.world_uid)
            writer = WorldPackWriter(paths)
            replace_region_index(writer.manifest,entries)
            writer.save_manifest()
            saved = paths.manifest_path().read_bytes()
            loaded = PackManifestStore().load(paths.manifest_path())
            self.assertEqual(loaded.wilderness_region_entries,entries)
            self.assertEqual(loaded.wilderness_region_entry(entries[0].region_uid),entries[0])
            writer.manifest.wilderness_region_entries.append(entries[0])
            with self.assertRaises(ValidationError):
                writer.save_manifest()
            self.assertEqual(paths.manifest_path().read_bytes(),saved)
            replace_region_index(writer.manifest,[])
            writer.save_manifest()
            self.assertEqual(PackManifestStore().load(paths.manifest_path()).wilderness_region_entries,[])
            self.assertEqual(WorldPackManifest.model_validate({"world_uid":"old"}).wilderness_region_entries,[])

    def test_seam_bbox_contains_canonical_parts_and_outline_is_derived(self):
        self.f.no_auto()
        self.f.declare(ForestSpec(name="seam",shape=BboxShape(x_min=14,y_min=2,x_max=18,y_max=5)))
        topology = self.f.topology.model_copy(update={"mode":source_fixture.WorldTopologyMode.WRAPPED})
        inputs = replace(self.f.inputs,topology=topology)
        plugin = self.f.plugin(topology=topology)
        regions = plugin.collect(self.f.ctx,self.f.policy)
        entry = build_region_index(regions,self.f.scale, registry=self.f.registry)[0]
        self.assertEqual((entry.bbox.x_min,entry.bbox.x_max),(0,15))
        outline = render_region_outline(self.f.ctx, inputs, entry.region_uid)
        self.assertIn("#",outline)
        self.assertIn("derived L0",outline)


class WildernessRegionBakeAndHttpTests(unittest.TestCase):
    def test_bake_publishes_index_and_selector_marks_snapshot_and_returns_404(self):
        f = bake_fixture.LandcoverContributorTests()
        f.setUp()
        f.declare(ForestSpec(name="indexed",shape=BboxShape(x_min=0,y_min=0,x_max=8,y_max=8)))
        # The legacy fixture has no region declarations. Add an explicit test region
        # and bound the bake to small tiles; preserve its world data and identity.
        raw = json.loads((Path(__file__).resolve().parents[2]/"fixtures/world_test_002.json").read_text(encoding="utf-8"))["world"]
        allowed = {field.name for field in fields(World)} - {"world_uid","name","created_at"}
        world = World(world_uid=raw["world_uid"],name=raw["name"],created_at=raw.get("created_at","test"),
                      **{key:value for key,value in raw.items() if key in allowed})
        world.world_topology_mode = "planar"
        world.world_bounds = f.world.world_bounds
        world.terrain_masks = f.world.terrain_masks
        from tests.planning.consumers.test_wiring import planning_kwargs
        deps = planning_kwargs(self)
        world.map_settings = {"global_cell_size_m": f.ctx.scale.tile_macro}
        world.fine_cells_per_map_cell = f.ctx.scale.tile_macro
        world.world_map_cells_per_tile = f.ctx.scale.side
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp)/"game.db")
            paths = WorldPackPaths.from_db_parent(db,world.world_uid)
            writer = WorldPackWriter(paths)
            # Exercise the production compose→index→writer path, with unrelated contributors omitted.
            from app.application.worldData.pack.bake.lightGrid.bake import compose_light_grid
            from app.application.worldData.pack.bake.lightGrid.contributors.landcover import LandcoverContributor
            def compose(ctx):
                return compose_light_grid(ctx,contributors=(LandcoverContributor(),))
            with patch("app.application.worldData.pack.bake.l0.worldMapBakeOrchestrator.compose_light_grid",side_effect=compose):
                WorldMapBakeOrchestrator().bake_tiles(world,[],writer,[(0,0)],surface_bundle=frozen_surface_fixture(world),wait=RequestPlanWait.unbounded(),region_state_snapshot={}, working=working_fixture(world, frozen_surface_fixture(world)))
            writer.save_manifest()
            uid = region_uid(world.world_uid,name="indexed")
            self.assertIsNotNone(writer.manifest.wilderness_region_entry(uid))
            context = PackReadContext(world.world_uid,db_path=db)
            world.terrain_pack_path = str(paths.root)
            world.terrain_pack_hash = writer.manifest.content_hash
            service = WildernessRegionReadService(context)
            self.assertTrue(service.get_snapshot(world,uid).snapshot)
            container = MagicMock()
            container.surface_planning_entry.return_value = SurfacePlanningEntry(deps["planning"], deps["capture"])
            container.region_state_repository.return_value.get_by_world = AsyncMock(return_value=[])
            container.world_service.return_value.get_by_id = AsyncMock(return_value=world)
            container.map_cell_read_service.return_value.pack.context = context
            container.location_service.return_value.get_all = AsyncMock(return_value=[])
            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_container] = lambda:container
            with TestClient(app) as client:
                self.assertEqual(client.get(f"/worlds/{world.world_uid}/map/regions/missing").status_code,404)
                response = client.get(f"/worlds/{world.world_uid}/map/regions/{uid}")
                self.assertEqual(response.status_code,200)
                self.assertTrue(response.json()["snapshot"])
                with patch.object(container.surface_planning_entry.return_value, "require_plan_inputs",
                           return_value=(frozen_surface_fixture(world), working_fixture(world, frozen_surface_fixture(world)))):
                    response = client.get(f"/worlds/{world.world_uid}/map/regions/{uid}/outline")
                self.assertEqual(response.status_code,200,response.text)
                self.assertIn("#",response.json()["outline"])
                self.assertEqual(response.json()["source"],"derived_world_data")
                f.declare()
                world.terrain_masks = f.world.terrain_masks
                with patch.object(container.surface_planning_entry.return_value, "require_plan_inputs",
                           return_value=(frozen_surface_fixture(world), working_fixture(world, frozen_surface_fixture(world)))):
                    stale = client.get(f"/worlds/{world.world_uid}/map/regions/{uid}/outline")
                self.assertEqual(stale.status_code,409)
                self.assertTrue(client.get(f"/worlds/{world.world_uid}/map/regions/{uid}").json()["snapshot"])

            # A subsequent bake with no regions must remove stale entries.
            f.declare()
            world.terrain_masks = f.world.terrain_masks
            with patch("app.application.worldData.pack.bake.l0.worldMapBakeOrchestrator.compose_light_grid",side_effect=compose):
                WorldMapBakeOrchestrator().bake_tile(world,0,0,writer,locations=[],wait=RequestPlanWait.unbounded(),surface_bundle=frozen_surface_fixture(world),region_state_snapshot={}, working=working_fixture(world, frozen_surface_fixture(world)))
            self.assertEqual(writer.manifest.wilderness_region_entries,[])


class OutlineReadBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from tests.test_landcover_fine_paint import _world, _surface_ctx
        self.world = _world()
        self.working = working_fixture(self.world, _surface_ctx(self.world))
        self.context = MagicMock()
        self.context.reader_for.return_value.manifest = SimpleNamespace(
            fine_cells_per_map_cell=8, world_map_cells_per_tile=2)
        self.repo = MagicMock()
        self.repo.get_by_world = AsyncMock(return_value=[])
        self.entry = MagicMock(spec=SurfacePlanningEntry)
        self.service = WildernessRegionReadService(self.context, entry=self.entry, region_state_repo=self.repo)

    async def test_absent_pack_or_membership_does_no_preparation_or_state_read(self):
        for has_pack in (False, True):
            self.context.has_pack_for.return_value = has_pack
            self.context.reader_for.return_value.manifest.wilderness_region_entry = lambda uid: None
            with patch("app.application.worldData.pack.read.wildernessRegionReadService.SurfacePlanningEntry") as entry:
                self.assertIsNone(await self.service.outline(self.world, [], "missing", wait=RequestPlanWait.unbounded()))
            entry.assert_not_called()
            self.entry.require_plan_inputs.assert_not_called()
        self.repo.get_by_world.assert_not_awaited()

    async def test_present_prepares_once_and_forwards_one_readonly_snapshot_to_render(self):
        self.service.get_snapshot = MagicMock(return_value=object())
        from app.application.worldData.regions.regionStateSnapshot import load_region_state_snapshot
        snapshots = []

        async def read_snapshot(repo, world_uid):
            snapshot = await load_region_state_snapshot(repo, world_uid)
            snapshots.append(snapshot)
            return snapshot

        with patch.object(self.entry, "require_plan_inputs",
                   return_value=(object(), self.working)) as prepare, patch(
                   "app.application.worldData.pack.read.wildernessRegionReadService.SurfacePlanningEntry",
                   side_effect=AssertionError("service must use injected entry")), patch(
                   "app.application.worldData.pack.read.wildernessRegionReadService.load_region_state_snapshot",
                   side_effect=read_snapshot) as load, patch(
                   "app.application.worldData.pack.read.wildernessRegionReadService.render_region_outline",
                   return_value="# outline") as render:
            result = await self.service.outline(self.world, [], "r", wait=RequestPlanWait.unbounded())
        self.assertEqual(result.outline, "# outline")
        prepare.assert_called_once()
        load.assert_awaited_once_with(self.repo, self.world.world_uid)
        self.repo.get_by_world.assert_awaited_once_with(self.world.world_uid)
        ctx, inputs, uid = render.call_args.args
        from app.application.worldData.generators.terrain.landcover.types import LandcoverCollectContext
        self.assertIsInstance(ctx, LandcoverCollectContext)
        self.assertIs(ctx.world, self.world)
        self.assertIs(inputs.topology, self.working.landcover.topology)
        self.assertIs(inputs.state_snapshot, snapshots[0])
        self.assertEqual((ctx.locations, ctx.tiles, uid), ((), (), "r"))
        with self.assertRaises(TypeError):
            inputs.state_snapshot["new"] = StateSnapshotEntry("forest")

    async def test_missing_repository_is_explicit_and_stale_geometry_preserves_error(self):
        from app.application.worldData.pack.read.wildernessRegionReadService import RegionOutlineStaleError
        self.service.get_snapshot = MagicMock(return_value=object())
        with patch.object(self.entry, "require_plan_inputs",
                   return_value=(object(), self.working)) as prepare:
            with self.assertRaises(RegionOutlineStaleError):
                await self.service.outline(self.world, [], "missing-geometry", wait=RequestPlanWait.unbounded())
            self.service._region_state_repo = None
            with self.assertRaisesRegex(ValueError, "repository required"):
                await self.service.outline(self.world, [], "r", wait=RequestPlanWait.unbounded())
            prepare.assert_called_once()
        self.repo.get_by_world.assert_awaited_once()

    async def test_no_extent_never_reads_region_state(self):
        self.service.get_snapshot = MagicMock(return_value=object())
        with patch.object(self.entry, "require_plan_inputs",
                   side_effect=ValueError("surface terrain context unavailable")):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                await self.service.outline(self.world, [], "r", wait=RequestPlanWait.unbounded())
        self.repo.get_by_world.assert_not_awaited()

    async def test_present_outline_requires_an_injected_entry(self):
        service = WildernessRegionReadService(self.context, region_state_repo=self.repo)
        service.get_snapshot = MagicMock(return_value=object())
        with self.assertRaisesRegex(ValueError, "surface planning entry required"):
            await service.outline(self.world, [], "r", wait=RequestPlanWait.unbounded())
        self.repo.get_by_world.assert_not_awaited()

    async def test_real_prepare_and_cached_plan_still_read_fresh_state_for_each_outline(self):
        from tests.planning.consumers.test_wiring import planning_kwargs
        from tests.test_landcover_fine_paint import _world
        from app.application.worldData.regions.regionStateMapping import state_to_row
        from app.dataModel.regions.regionState import RegionState
        from app.application.worldData.pack.read.wildernessRegionReadService import RegionOutlineStaleError

        source = _world(ForestSpec(name="woods", shape=BboxShape(x_min=0, y_min=0, x_max=5, y_max=6)))
        allowed = {field.name for field in fields(World)} - {"world_uid", "name", "created_at"}
        self.world = World(world_uid=source.world_uid, name="outline", created_at="now",
            **{key: value for key, value in vars(source).items() if key in allowed})
        uid = region_uid(self.world.world_uid, name="woods")
        deps = planning_kwargs(self)
        service = WildernessRegionReadService(self.context, region_state_repo=self.repo,
            entry=SurfacePlanningEntry(deps["planning"], deps["capture"]))
        service.get_snapshot = MagicMock(return_value=object())
        first = await service.outline(self.world, [], uid, wait=RequestPlanWait.unbounded())
        self.assertIn("#", first.outline)
        state = RegionState(region_uid=uid, current_type="forest", tombstone=True)
        self.repo.get_by_world.return_value = [state_to_row(state, world_uid=self.world.world_uid,
            created_at="then", updated_at="now")]
        with self.assertRaises(RegionOutlineStaleError):
            await service.outline(self.world, [], uid, wait=RequestPlanWait.unbounded())
        self.assertEqual(self.repo.get_by_world.await_count, 2)


if __name__ == "__main__":
    unittest.main()
