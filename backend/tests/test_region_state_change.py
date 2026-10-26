"""10a: real scorer, explicit elapsed, child identity and repository boundary."""

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from app.application.worldData.regions.coverageResolver import TargetCoverage
from app.application.worldData.regions.factConsumers import FactConsumer
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import ClimateFacts, DeclarationFacts
from app.application.worldData.regions.regionStateMapping import state_from_row, state_to_row
from app.application.worldData.regions.stateChange.consumer import StateChangeConsumer, child_uid
from app.application.worldData.regions.stateChange.contracts import RegionEvaluation, SpatialEvaluation
from app.application.worldData.regions.stateChange.progress import advance
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.regions.regionState import RegionState, RegionStateOverrides, RegionTransitionCause
from app.dataModel.spatial.regionShape import BboxShape, EdgeNoise
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.enums.eligibilityOp import EligibilityOp
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import (
    LandcoverRegionsCategoryPolicy, LandcoverTerrainPolicy)
from app.dataModel.terrainMasks.regions import RegionSpecBase
from app.db.repositories.iRegionStateRepository import IRegionStateRepository
from app.db.database import Database
from app.db.repositories.sqlite.regionStateRepository import SqliteRegionStateRepository


def registry():
    return WorldTerrainRegistry([
        TerrainRegistryEntry(system_terrain="forest", terrain_category="solid", inertia=4,
            merge_rank=2, eligibility=[EligibilityRule(fact="climate.rainfall",
                op=EligibilityOp.GTE, lo=50, required=True)]),
        TerrainRegistryEntry(system_terrain="steppe", terrain_category="solid", merge_rank=2,
            eligibility=[EligibilityRule(fact="climate.rainfall",
                op=EligibilityOp.LTE, hi=10, required=True)]),
        TerrainRegistryEntry(system_terrain="lowland_lake", terrain_category="liquid",
            morph_hydrology_role=HydrologyCellRole.LAKE, merge_rank=3,
            eligibility=[EligibilityRule(fact="climate.rainfall",
                op=EligibilityOp.GTE, lo=200, weight=5, required=True)]),
    ])


def policy(**changes):
    return LandcoverRegionsCategoryPolicy(seed_spacing=4, max_radius=7,
        claim_noise=EdgeNoise(amplitude=1, scale=2), **changes)


class ProgressTests(unittest.TestCase):
    def advance(self, state, target="steppe", strength=1, elapsed=1, declaration=None, **changes):
        return advance(state, TargetCoverage(target, strength) if target else None,
            registry=registry(), policy=policy(**changes), elapsed_ticks=elapsed,
            declaration=declaration, cause=RegionTransitionCause.DRIFT, at=42)

    def test_drift_accumulation_threshold_and_append_only_history(self):
        state = RegionState(region_uid="r", current_type="forest")
        states = [state]
        for _ in range(4):
            states.append(self.advance(states[-1]))
        self.assertEqual([s.progress for s in states], [0, .25, .5, .75, 0])
        self.assertEqual(states[-1].current_type, "steppe")
        self.assertEqual(states[-1].region_uid, state.region_uid)
        self.assertEqual(states[-1].last_eval_tick, 4)
        self.assertEqual(states[-1].history[0].at, 42)
        self.assertEqual(states[-1].history[0].cause, RegionTransitionCause.DRIFT)
        self.assertEqual(state.history, ())
        returned = self.advance(states[-1], "forest", elapsed=1)
        self.assertEqual(returned.history[:1], states[-1].history)
        self.assertEqual(len(returned.history), 2)

    def test_hysteresis_strength_declaration_and_policy_threshold(self):
        state = RegionState(region_uid="r", current_type="forest",
                            pending_target="lowland_lake", progress=.75)
        switched = self.advance(state)
        self.assertEqual(switched.pending_target, "steppe")
        self.assertEqual(switched.progress, .25)
        self.assertEqual(switched.current_type, "forest")
        self.assertEqual(self.advance(state, strength=.5).progress, .125)
        self.assertEqual(self.advance(state, declaration=DeclarationFacts(True, 4)).progress, .125)
        self.assertEqual(self.advance(state, transition_threshold=.2).current_type, "steppe")
        self.assertEqual(self.advance(state, target="forest").progress, .5)
        self.assertIsNone(self.advance(state, target="forest", elapsed=4).pending_target)

    def test_unresolved_zero_elapsed_tombstone_and_invalid_elapsed(self):
        state = RegionState(region_uid="r", current_type="forest", progress=.5, pending_target="steppe")
        self.assertEqual(self.advance(state, target=None).progress, .5)
        self.assertEqual(self.advance(state, elapsed=0).progress, .5)
        dead = state.model_copy(update={"tombstone": True})
        self.assertEqual(self.advance(dead), dead)
        for elapsed in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                self.advance(state, elapsed=elapsed)

    def test_threshold_and_morph_metadata_validate(self):
        for threshold in (0, -1, 2, float("inf"), float("nan")):
            with self.assertRaises(ValidationError):
                policy(transition_threshold=threshold)
        with self.assertRaises(ValidationError):
            TerrainRegistryEntry(system_terrain="r", terrain_category="liquid",
                                 morph_hydrology_role=HydrologyCellRole.RIVER_BED)


class ConsumerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rows = {}
        self.repo = AsyncMock(spec=IRegionStateRepository)
        self.repo.get_many.side_effect = self.get_many
        self.repo.upsert_bulk.side_effect = self.store
        self.consumer = StateChangeConsumer(self.repo, registry=registry(), policy=policy())
        # Exercise the existing collector and real scorer, varying observations by scope.
        self.plugin = FactConsumer("climate", lambda context, facts: replace(facts,
            climate=ClimateFacts(rainfall_mean=float(context.cells[0][0]))))
        from app.application.worldData.regions.factConsumers import collect_facts
        self.collector = patch("app.application.worldData.regions.stateChange.consumer.collect_facts",
            side_effect=lambda *args, **kwargs: collect_facts(*args, **kwargs, consumers=(self.plugin,)))
        self.collector.start()
        self.addCleanup(self.collector.stop)

    async def get_many(self, world, uids):
        return [self.rows[world, uid] for uid in uids if (world, uid) in self.rows]

    async def store(self, rows):
        for row in rows:
            self.rows[row.world_uid, row.region_uid] = row
        return len(rows)

    def request(self, **changes):
        spec = RegionSpecBase(name="forest", shape=BboxShape(x_min=0, y_min=0, x_max=20, y_max=20),
                              placement_specificity=3)
        return replace(RegionEvaluation(region_uid="r", entry_type="forest", spec=spec,
            spec_fingerprint="v1", context=FactConsumerContext(cells=((0, 0),)),
            elapsed_ticks=1, at=42, updated_at="now"), **changes)

    async def seed(self, **changes):
        state = RegionState(region_uid="r", current_type="forest", spec_fingerprint="v1", **changes)
        await self.store([state_to_row(state, world_uid="w", created_at="then", updated_at="then")])
        return state

    async def test_real_scorer_progress_logs_after_persist_and_no_progress_signal(self):
        await self.seed()
        with patch("app.application.worldData.regions.stateChange.consumer.log_transition") as log:
            for i in range(4):
                result = await self.consumer.evaluate("w", self.request())
                if i < 3:
                    self.assertEqual(result.materialize, ())
            log.assert_called_once()
        self.assertEqual(result.state.current_type, "steppe")
        self.assertEqual(len(result.materialize), 1)
        self.assertEqual(self.rows["w", "r"].created_at, "then")
        self.repo.upsert.assert_not_called()

    async def test_partial_child_reuses_uid_progress_specificity_and_parent_type(self):
        await self.seed()
        request = self.request()
        part = SpatialEvaluation(seed_xy=(2, 2), spec=RegionSpecBase(
            shape=BboxShape(x_min=1, y_min=1, x_max=3, y_max=3)), context=request.context)
        request = replace(request, spatial=(part,))
        for _ in range(4):
            result = await self.consumer.evaluate("w", request)
        child = result.children[0]
        self.assertEqual(result.state.current_type, "forest")
        self.assertEqual(child.state.current_type, "steppe")
        self.assertEqual(child.parent_region_uid, "r")
        self.assertNotEqual(child.region_uid, "r")
        self.assertEqual(child.spec.placement_specificity, 4)
        self.assertNotEqual(child.region_uid, child_uid("w", "other", part.seed_xy))
        replay = replace(request, spatial=(replace(part, spec=child.spec),), elapsed_ticks=0)
        again = await self.consumer.evaluate("w", replay)
        self.assertEqual(again.children[0].state, child.state)
        self.assertEqual(self.repo.upsert_bulk.call_args.args[0][0].region_uid, "r")
        self.assertEqual(len(self.repo.upsert_bulk.call_args.args[0]), 2)

    async def test_morph_signals_lake_metadata_without_touching_cells(self):
        await self.seed()
        result = await self.consumer.evaluate("w", self.request(
            context=FactConsumerContext(cells=((400, 0),)), elapsed_ticks=4))
        self.assertEqual(result.state.current_type, "lowland_lake")
        self.assertFalse(result.state.tombstone)
        self.assertEqual(result.materialize[0].target.morph_hydrology_role, HydrologyCellRole.LAKE)
        self.assertEqual(result.materialize[0].spec, self.request().spec)

    async def test_declared_shape_and_type_reset_then_tombstone_is_preserved(self):
        await self.seed(progress=.75, pending_target="steppe")
        changed = self.request(spec_fingerprint="v2", declaration=DeclarationFacts(True, 2),
                               previous_entry_type="forest")
        result = await self.consumer.evaluate("w", changed)
        self.assertEqual(result.state.current_type, "forest")
        self.assertEqual(result.state.progress, 0)
        result = await self.consumer.evaluate("w", replace(changed,
            spec_fingerprint="v3", entry_type="steppe"))
        self.assertEqual(result.state.current_type, "steppe")
        self.assertEqual(result.state.history[-1].cause, RegionTransitionCause.DECLARED_EDIT)
        self.rows["w", "r"].tombstone = True
        result = await self.consumer.evaluate("w", self.request())
        self.assertTrue(result.state.tombstone)
        self.assertEqual(state_from_row(self.rows["w", "r"]), result.state)

    async def test_density_world_isolation_and_invalid_revision_does_not_write(self):
        await self.seed()
        result = await self.consumer.evaluate("w", self.request(elapsed_ticks=0,
            overrides=RegionStateOverrides(density=.9)))
        self.assertEqual(result.state.overrides.density, .9)
        self.assertEqual(len(result.materialize), 1)
        count = self.repo.upsert_bulk.call_count
        with self.assertRaises(ValueError):
            await self.consumer.evaluate("w", self.request(spec_fingerprint="v2",
                declaration=DeclarationFacts(True, 2)))
        self.assertEqual(self.repo.upsert_bulk.call_count, count)
        result = await self.consumer.evaluate("other", self.request(elapsed_ticks=0))
        self.assertEqual(result.state.overrides, None)

    async def test_persist_failure_never_logs_transition(self):
        await self.seed()
        self.repo.upsert_bulk.side_effect = RuntimeError("storage failed")
        with patch("app.application.worldData.regions.stateChange.consumer.log_transition") as log:
            with self.assertRaises(RuntimeError):
                await self.consumer.evaluate("w", self.request(elapsed_ticks=4))
            log.assert_not_called()

    async def test_real_sqlite_batch_round_trip_and_explicit_tombstone(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(str(Path(directory) / "region.sqlite"))
            await db.connect()
            try:
                await db.apply_migrations()
                async with db.transaction():
                    await db.conn.execute(
                        "INSERT INTO worlds(world_uid, name, created_at) VALUES ('w', 'W', 'now')")
                repo = SqliteRegionStateRepository(db)
                consumer = StateChangeConsumer(repo, registry=registry(), policy=policy())
                request = self.request()
                part = SpatialEvaluation(seed_xy=(1, 1), spec=RegionSpecBase(
                    shape=BboxShape(x_min=1, y_min=1, x_max=2, y_max=2)), context=request.context)
                for _ in range(4):
                    result = await consumer.evaluate("w", replace(request, spatial=(part,)))
                stored = {row.region_uid: state_from_row(row) for row in await repo.get_by_world("w")}
                child = result.children[0]
                self.assertEqual(stored["r"].current_type, "forest")
                self.assertEqual(stored[child.region_uid], child.state)
                self.assertEqual(len(child.state.history), 1)
                self.assertEqual(await consumer.tombstone("w", "r", updated_at="later"), 1)
                self.assertTrue((await consumer.evaluate("w", request)).state.tombstone)
            finally:
                await db.disconnect()

    async def test_unresolved_facts_keep_progress_and_absent_children_are_not_removed(self):
        original = await self.seed(progress=.25, pending_target="steppe")
        result = await self.consumer.evaluate("w", self.request(context=FactConsumerContext(cells=((30, 0),))))
        self.assertEqual(result.state.current_type, original.current_type)
        self.assertEqual(result.state.progress, original.progress)
        self.repo.mark_tombstone.assert_not_called()

    async def test_policy_closed_keys_are_not_drift_targets(self):
        for closed in (dict(enabled=False), dict(autoresolve=False)):
            with self.subTest(**closed):
                pol = policy(terrain_policies={"steppe": LandcoverTerrainPolicy(
                    system_terrain="steppe", **closed)})
                consumer = StateChangeConsumer(self.repo, registry=registry(), policy=pol)
                self.rows.clear()
                await self.seed()
                with self.assertLogs("app.application.worldData.regions.coverageResolver",
                                     level="WARNING") as logs:
                    for _ in range(4):
                        result = await consumer.evaluate("w", self.request())
                self.assertEqual(result.state.current_type, "forest")
                self.assertIsNone(result.state.pending_target)
                self.assertEqual(result.state.progress, 0)
                self.assertEqual(result.materialize, ())
                self.assertTrue(any("resolve_unresolved" in line
                                    and "reason=no_eligible_candidates" in line
                                    for line in logs.output))

    async def test_entry_without_eligibility_is_not_a_candidate_but_remains_a_known_key(self):
        reg = WorldTerrainRegistry([*registry().root,
            TerrainRegistryEntry(system_terrain="bare", terrain_category="solid", merge_rank=2)])
        consumer = StateChangeConsumer(self.repo, registry=reg, policy=policy())
        await self.seed()
        with self.assertLogs("app.application.worldData.regions.coverageResolver",
                             level="WARNING") as logs:
            result = await consumer.evaluate("w", self.request(
                context=FactConsumerContext(cells=((30, 0),))))
        self.assertTrue(any("reason=no_eligible_candidates" in line for line in logs.output))
        self.assertEqual(result.state.current_type, "forest")
        self.assertIsNone(result.state.pending_target)
        result = await consumer.evaluate("w", self.request(region_uid="b",
            entry_type="bare", context=FactConsumerContext(cells=((30, 0),))))
        self.assertEqual(result.state.current_type, "bare")
        self.assertEqual([e.system_terrain for e in consumer._candidates.root],
                         ["forest", "steppe", "lowland_lake"])

    async def test_none_specificity_child_wins_equal_rank_and_slow_declaration(self):
        request = self.request(declaration=DeclarationFacts(True, 4))
        spec = request.spec.model_copy(update={"placement_specificity": None})
        part = SpatialEvaluation(seed_xy=(1, 1), spec=spec, context=request.context)
        result = await self.consumer.evaluate("w", replace(request, spec=spec, spatial=(part,)))
        self.assertEqual(result.children[0].spec.placement_specificity, 0)
        self.assertEqual(result.children[0].state.progress, .125)


if __name__ == "__main__":
    unittest.main()
