"""9b: typed state, actual repository read, scoped revision repaint and death."""

from tests.planning.consumers.test_wiring import working_fixture
from dataclasses import replace
from pathlib import Path
import tempfile
from app.application.cancellation.requestPlanWait import RequestPlanWait
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError

from app.application.worldData.generators.terrain.landcover.collect import resolve_collected
from app.application.worldData.generators.terrain.landcover.types import AnchoredRegion, StateSnapshotEntry
from app.application.worldData.materialize.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.application.worldData.materialize.materializationContext import MaterializationContext
from app.application.worldData.pack.bake.packMaterializationOrchestrator import PackMaterializationOrchestrator
from app.application.worldData.pack.refine.fine.fineChunkRunner import FineChunkRunner
from app.application.worldData.pack.bake.wildernessRegionIndex import build_region_index
from app.application.worldData.regions.regionStateMapping import state_from_row, state_to_row
from app.application.worldData.regions.regionStateSnapshot import load_region_state_snapshot
from app.dataModel.regions.regionState import (
    RegionState, RegionStateOverrides, RegionStateTransition, RegionTransitionCause,
)
from app.dataModel.registryKey import RegistryKey
from app.dataModel.spatial.regionShape import AnchorRadiusShape, BboxShape
from app.dataModel.terrainMasks.regions import ForestSpec, PlainSpec
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry
from app.db.database import Database
from app.db.repositories.sqlite.regionStateRepository import SqliteRegionStateRepository
from app.db.repositories.iRegionStateRepository import IRegionStateRepository
from app.ids import state_fingerprint
from tests import test_landcover_materializer as light
from tests import test_landcover_fine_paint as fine


class RegionStateContractTests(unittest.TestCase):
    def test_renamed_field_serializes_spec_and_rejects_historical_key(self):
        state = self.state(spec_fingerprint="revision")
        self.assertIn("spec_fingerprint", state.model_dump())
        self.assertNotIn("state_fingerprint", state.model_dump())
        with self.assertRaises(ValidationError):
            WildernessRegionEntry.model_validate({
                "region_uid": "r", "entry_type": "forest", "current_type": "steppe",
                "bbox": {"x_min": 0, "y_min": 0, "x_max": 2, "y_max": 2},
                "status": "declared", "state_fingerprint": "historical-revision",
            })
        entry = WildernessRegionEntry.model_validate({
            "region_uid": "r", "entry_type": "forest", "current_type": "steppe",
            "bbox": {"x_min": 0, "y_min": 0, "x_max": 2, "y_max": 2},
            "status": "declared", "spec_fingerprint": "historical-revision",
        })
        self.assertEqual(entry.spec_fingerprint, "historical-revision")
        self.assertNotIn("state_fingerprint", entry.model_dump())

    def state(self, **changes):
        return RegionState(region_uid="r", current_type="steppe", pending_target="swamp",
                           overrides=RegionStateOverrides(density=0.6),
                           history=(RegionStateTransition(from_type="forest", to_type="steppe",
                               cause=RegionTransitionCause.DRIFT, at=42),), **changes)

    def test_typed_row_and_json_round_trip(self):
        state = self.state(progress=0.4, spec_fingerprint="revision")
        row = state_to_row(state, world_uid="w", created_at="then", updated_at="now")
        self.assertIsInstance(row.overrides, dict)
        self.assertIsInstance(row.history, list)
        self.assertEqual(row.history[0]["cause"], "drift")
        restored = state_from_row(row)
        self.assertEqual(restored, state)
        self.assertIsInstance(restored.current_type, RegistryKey)
        self.assertIsInstance(restored.pending_target, RegistryKey)
        self.assertIsInstance(restored.history[0].from_type, RegistryKey)
        self.assertIsInstance(restored.history[0].cause, RegionTransitionCause)
        self.assertEqual(RegionState.model_validate_json(state.model_dump_json()), state)
        empty = RegionState(region_uid="r", current_type="forest")
        self.assertEqual(state_from_row(state_to_row(empty, world_uid="w",
            created_at="then", updated_at="now")), empty)

    def test_invalid_values_are_rejected(self):
        for progress in (-0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(progress=progress), self.assertRaises(ValidationError):
                self.state(progress=progress)
        for density in (-1, 2, float("nan")):
            with self.assertRaises(ValidationError):
                RegionStateOverrides(density=density)
        row = state_to_row(self.state(), world_uid="w", created_at="then", updated_at="now")
        row.history[0]["cause"] = "arbitrary"
        with self.assertRaises(ValidationError):
            state_from_row(row)
        row.overrides = {"unknown": 1}
        with self.assertRaises(ValidationError):
            state_from_row(row)

    def test_history_prefix_is_immutable_and_append_creates_new_state(self):
        state = self.state()
        with self.assertRaises(AttributeError):
            state.history.append(state.history[0])
        with self.assertRaises(ValidationError):
            state.history[0].at = 50
        row = state_to_row(state, world_uid="w", created_at="then", updated_at="now")
        row.history.append({"from_type": "steppe", "to_type": "swamp", "cause": "event", "at": "fire"})
        updated = state_from_row(row)
        self.assertEqual(updated.history[:len(state.history)], state.history)
        self.assertEqual(len(state.history), 1)


class RegionRevisionTests(unittest.TestCase):
    def setUp(self):
        self.f = light.LandcoverMaterializerTests()
        self.f.setUp()
        self.f.no_auto()
        self.old = ForestSpec(name="woods", shape=BboxShape(x_min=0, y_min=0, x_max=15, y_max=7))
        self.f.declare(self.old)
        self.initial = self.f.plugin().collect(self.f.ctx, self.f.policy)[0]

    def test_match_keeps_state_and_mismatch_repaints_only_current_tile(self):
        old = StateSnapshotEntry(self.f.plains, False, self.initial.spec_fingerprint)
        snapshot = {self.initial.region_uid: old}
        plugin = self.f.plugin(state_snapshot=snapshot)
        before = self.f.paint(plugin)
        self.assertFalse(plugin.resolved_regions[0].revision_changed)
        self.assertEqual(plugin.resolved_regions[0].spec_fingerprint,
                         state_fingerprint(self.old.model_dump(mode="json")))
        # Shape edits preserve simulated type but move the painted footprint.
        new = self.old.model_copy(update={"shape": BboxShape(x_min=8, y_min=0, x_max=15, y_max=3)})
        self.f.declare(new)
        partial_ctx = replace(self.f.ctx, tiles=[(1, 0)])
        plugin = self.f.plugin(state_snapshot=snapshot)
        with self.assertLogs("app.application.worldData.generators.terrain.landcover.collect", level="DEBUG") as logs:
            after = self.f.paint(plugin, partial_ctx)
        region = plugin.resolved_regions[0]
        self.assertTrue(region.revision_changed)
        self.assertEqual(region.current_type, self.f.plains)
        self.assertEqual(region.entry_type, self.f.forest)
        self.assertEqual({key[:2] for key in after}, {(1, 0)})
        self.assertNotEqual(after, {k: v for k, v in before.items() if k[:2] == (1, 0)})
        self.assertIn("revision_mismatch", " ".join(logs.output))
        self.assertIs(snapshot[region.region_uid], old)
        full = self.f.paint(self.f.plugin(state_snapshot=snapshot))
        self.assertEqual(after, {k: v for k, v in full.items() if k[:2] == (1, 0)})

    def test_unknown_revision_mismatches_and_tombstone_never_materializes(self):
        inputs = replace(self.f.inputs, state_snapshot={self.initial.region_uid: StateSnapshotEntry(self.f.plains)})
        self.assertTrue(resolve_collected([self.initial], self.f.ctx, inputs, self.f.registry)[0].revision_changed)
        plugin = self.f.plugin(state_snapshot={self.initial.region_uid: StateSnapshotEntry(self.f.plains, True)})
        self.assertEqual(plugin.collect(self.f.ctx, self.f.policy), [])

    def test_type_edit_signals_writer_without_resetting_simulated_type(self):
        self.f.declare(PlainSpec(name="woods", shape=self.old.shape))
        plugin = self.f.plugin(state_snapshot={self.initial.region_uid:
            StateSnapshotEntry(self.f.forest, False, self.initial.spec_fingerprint)})
        region = plugin.collect(self.f.ctx, self.f.policy)[0]
        self.assertEqual(region.region_uid, self.initial.region_uid)
        self.assertTrue(region.revision_changed)
        self.assertEqual(region.current_type, self.f.forest)
        self.assertEqual(region.entry_type, self.f.plains)

    def test_anchor_revision_uses_authored_wire_in_collect_and_index(self):
        spec = ForestSpec(shape=AnchorRadiusShape(anchor_uid="anchor", radius=2))
        ctx = replace(self.f.ctx, locations=[type("Location", (), {
            "location_uid": "anchor", "map_x": 5, "map_y": 5})()])
        self.f.declare()
        plugin = self.f.plugin(anchor_specs=(AnchoredRegion("anchor", spec),))
        region = plugin.collect(ctx, self.f.policy)[0]
        fingerprint = state_fingerprint(spec.model_dump(mode="json"))
        self.assertEqual(region.spec_fingerprint, fingerprint)
        entries = build_region_index([region], self.f.scale, registry=self.f.registry)
        self.assertEqual(entries[0].spec_fingerprint, fingerprint)
        plugin = self.f.plugin(anchor_specs=(AnchoredRegion("anchor", spec),),
            state_snapshot={region.region_uid: StateSnapshotEntry(self.f.forest, False, fingerprint)})
        self.assertFalse(plugin.collect(ctx, self.f.policy)[0].revision_changed)

    def test_fine_tombstone_restores_last_parent_region_to_background(self):
        world = fine._world(ForestSpec(name="woods", shape=self.old.shape))
        uid = fine.region_uid(world.world_uid, name="woods")
        state = TerrainBatchOrchestrator(MagicMock()).build_tile_surface_state(
            world, [], fine._surface_ctx(world), 0, 0, parent_light=fine._parent(),
            region_state_snapshot={uid: StateSnapshotEntry(fine.FOREST, True)}, working=working_fixture(world, fine._surface_ctx(world)))
        self.assertFalse(state.surface_region_uid)
        self.assertEqual(set(state.surface_terrain.values()), {fine.PLAINS})

    def test_fine_mismatch_replaces_stale_parent_type_and_geometry(self):
        spec = ForestSpec(name="woods", shape=BboxShape(x_min=4, y_min=4, x_max=5, y_max=5))
        world = fine._world(spec)
        uid = fine.region_uid(world.world_uid, name="woods")
        state = TerrainBatchOrchestrator(MagicMock()).build_tile_surface_state(
            world, [], fine._surface_ctx(world), 0, 0, parent_light=fine._parent(),
            region_state_snapshot={uid: StateSnapshotEntry(fine.PLAINS, False, "old-revision")}, working=working_fixture(world, fine._surface_ctx(world)))
        self.assertEqual(state.surface_region_uid, {(x, y): uid for x in (4, 5) for y in (4, 5)})
        self.assertEqual(set(state.surface_terrain.values()), {fine.PLAINS})


class RegionStateReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_owners_forward_repository_snapshot_before_compute(self):
        class ComputeBoundary(Exception):
            pass

        world = fine._world()
        state = RegionState(region_uid="r", current_type="plains", spec_fingerprint="old")
        repo = AsyncMock(spec=IRegionStateRepository)
        repo.get_by_world.return_value = [state_to_row(state, world_uid=world.world_uid,
            created_at="then", updated_at="now")]
        mat_ctx = MaterializationContext(free_cores=1)
        terrain, writer = MagicMock(), MagicMock()
        climate = MagicMock()
        climate.bake_coarse = AsyncMock(return_value=(None, 0))
        entry, planner, world_map = MagicMock(), MagicMock(), MagicMock()
        entry.has_job_repo = False
        planner.plan.return_value.tile_tuples.return_value = [(0, 0)]
        planner.plan.return_value.cap_applied = None
        world_map.bake_tiles.side_effect = ComputeBoundary
        owner = PackMaterializationOrchestrator(terrain, world_map=world_map,
            entry=entry, climate_bake=climate, tile_planner=planner, region_state_repo=repo, planning=MagicMock(), capture=MagicMock())
        with patch("app.application.worldData.planning.composition.surfacePlanningEntry.SurfacePlanningEntry.prepare_captured",
                   return_value=(fine._surface_ctx(world), working_fixture(world, fine._surface_ctx(world)))), self.assertRaises(ComputeBoundary):
            await owner.materialize_light_pack(world.world_uid, world, [], writer, mat_ctx, wait=RequestPlanWait.unbounded())
        self.assertEqual(world_map.bake_tiles.call_args.kwargs["region_state_snapshot"]["r"].current_type, "plains")
        runner = FineChunkRunner(terrain, region_state_repo=repo)
        with patch("app.application.worldData.pack.refine.fine.fineChunkRunner.prepare_fine_tile",
                   side_effect=ComputeBoundary) as prep, self.assertRaises(ComputeBoundary):
            await runner.refine_rects(world, [], writer, mat_ctx, fine._surface_ctx(world),
                                     0, 0, [MagicMock()], [], working=working_fixture(world, fine._surface_ctx(world)))
        self.assertEqual(prep.call_args.kwargs["region_state_snapshot"]["r"].spec_fingerprint, "old")
        self.assertEqual(repo.get_by_world.await_count, 2)
        repo.upsert.assert_not_called()
        repo.upsert_bulk.assert_not_called()
        repo.mark_tombstone.assert_not_called()

    async def test_real_repository_to_collect_read_only_world_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(str(Path(tmp) / "state.db"))
            await db.connect()
            try:
                await db.apply_migrations()
                async with db.transaction():
                    await db.conn.execute("INSERT INTO worlds(world_uid,name,created_at) VALUES ('world','W','now')")
                repo = SqliteRegionStateRepository(db)
                state = RegionState(region_uid="r", current_type="plains", progress=0.5,
                                    spec_fingerprint="old")
                row = state_to_row(state, world_uid="world", created_at="now", updated_at="now")
                await repo.upsert(row)  # Test setup only; production reads never write.
                snapshot = await load_region_state_snapshot(repo, "world")
                self.assertEqual(snapshot["r"].current_type, "plains")
                self.assertEqual(snapshot["r"].spec_fingerprint, "old")
                f = light.LandcoverMaterializerTests()
                f.setUp()
                f.no_auto()
                f.declare(ForestSpec(name="woods", shape=BboxShape(x_min=0, y_min=0, x_max=3, y_max=3)))
                region = replace(f.plugin().collect(f.ctx, f.policy)[0], region_uid="r")
                result = resolve_collected([region], f.ctx, replace(f.inputs, state_snapshot=snapshot), f.registry)
                self.assertTrue(result[0].revision_changed)
                self.assertEqual(result[0].current_type, "plains")
                self.assertEqual(await repo.get("world", "r"), row)
                self.assertEqual(await load_region_state_snapshot(repo, "other"), {})
                self.assertEqual(await load_region_state_snapshot(None, "world"), {})
                await repo.mark_tombstone("world", "r", updated_at="later")
                self.assertTrue((await load_region_state_snapshot(repo, "world"))["r"].tombstone)
            finally:
                await db.disconnect()
