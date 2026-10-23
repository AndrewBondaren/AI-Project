"""P2 behavior: priority, dependency readiness, stable results and policy parity."""

from itertools import permutations
from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.worldData.placement import resolve_placements
from app.dataModel.placement import (
    PlacementBatch, PlacementCandidate, PlacementFootprint, PlacementIntent, PlacementIssueCode as Code,
    PreparedPlacement, ResolvedPlacement, UnresolvedPlacement,
)
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.planning.identity.planKey import OutputFingerprint

SNAPSHOT_REVISION = OutputFingerprint(sha256(b"test-pre-relief-surface").digest())


def variant(uid, cells, *, preference=0, z=(None, None)):
    return PlacementCandidate(candidate_uid=uid, preference=preference,
                              footprint=PlacementFootprint(cells=cells, z_min=z[0], z_max=z[1]))


def obj(uid, cells=((0, 0),), *, priority=0, area=1.0, mode="absolute", movement="forbid",
        candidates=None, dependencies=(), overlaps=(), separations=(), z=(None, None), auto=None, coastline=None):
    intent = PlacementIntent(identity={"world_uid": "world", "source_uid": f"source-{uid}", "region_uid": uid},
        mode=mode, shape=None, placement_specificity=priority, absolute_movement=movement,
        dependencies=dependencies, permitted_overlaps=overlaps, separations=separations)
    return PreparedPlacement(intent=intent, original_area=area,
        candidates=(variant(f"{uid}/fixed", cells, z=z),) if candidates is None else candidates,
        auto_specificity=auto, coastline=coastline)


def dep(uid, relation="resolved"):
    return {"target_uid": uid, "relation": relation}


def overlap(uid, relation="coverage"):
    return {"target_uid": uid, "relation": relation}


def separation(uid, xy=0, z=0):
    return {"target_uid": uid, "min_xy": xy, "min_z": z}


def topology(mode="planar", *, x_max=31, y_max=15):
    return WorldTopology(mode=mode, bounds=WorldBounds(x_min=0, x_max=x_max, y_min=0, y_max=y_max))


def batch(*objects, accepted=(), phase="pre_relief", world_topology=None):
    return PlacementBatch(world_uid="world", snapshot_uid="snapshot", phase=phase,
                          snapshot_revision=SNAPSHOT_REVISION,
                          topology=world_topology or topology(), objects=objects, accepted=accepted)


def solve(*objects, **kwargs):
    return resolve_placements(batch(*objects, **kwargs), ctx=ResolveContext(validate_only=True))


def outcomes(result):
    return {item.prepared.intent.identity.region_uid: item for item in result.results}


def codes(result, uid):
    return {item.code for item in outcomes(result)[uid].diagnostics}


class PlacementPriorityTests(unittest.TestCase):
    def test_priority_area_and_uid_ties_are_independent_of_object_order(self):
        cases = ((obj("a", priority=1, area=100), obj("b", priority=2), "b"),
                 (obj("a", area=1), obj("b", area=100), "b"),
                 (obj("a"), obj("b"), "a"))
        for left, right, winner in cases:
            expected = None
            for ordering in permutations((left, right)):
                result = solve(*ordering)
                with self.subTest(winner=winner, ordering=[x.intent.identity.region_uid for x in ordering]):
                    self.assertIsInstance(outcomes(result)[winner], ResolvedPlacement)
                    self.assertEqual(sum(isinstance(item, ResolvedPlacement) for item in result.results), 1)
                    if expected is not None:
                        self.assertEqual(result, expected)
                expected = result

    def test_semantic_candidates_use_preference_then_uid_without_failed_attempt_logs(self):
        alternatives = (variant("c", {(2, 0)}, preference=1), variant("b", {(1, 0)}, preference=1),
                        variant("a", {(0, 0)}, preference=0))
        for ordering in permutations(alternatives):
            result = solve(obj("occupied", priority=5), obj("semantic", mode="semantic", candidates=ordering))
            selected = outcomes(result)["semantic"]
            self.assertEqual(selected.candidate_uid, "b")
            self.assertEqual(selected.footprint.cells, frozenset({(1, 0)}))
            self.assertEqual(result.diagnostics, ())

    def test_absolute_conflict_does_not_shift_or_clip_and_explicit_alternatives_can_resolve(self):
        fixed = obj("fixed", priority=1)
        source = batch(obj("winner", priority=10), fixed)
        before = source.model_dump()
        result = resolve_placements(source, ctx=ResolveContext(validate_only=True))
        self.assertEqual(source.model_dump(), before)
        self.assertIsInstance(outcomes(result)["fixed"], UnresolvedPlacement)
        self.assertEqual(codes(result, "fixed"), {Code.SPATIAL_CONFLICT})
        self.assertFalse(hasattr(outcomes(result)["fixed"], "footprint"))
        explicit = obj("fixed", movement="explicit_candidates", candidates=(
            variant("initial", {(0, 0)}), variant("allowed", {(4, 0)}, preference=1)))
        resolved = solve(obj("winner", priority=10), explicit)
        self.assertEqual(outcomes(resolved)["fixed"].candidate_uid, "allowed")

    def test_missing_auto_and_empty_candidates_are_unresolved_without_error_defaults(self):
        result = solve(obj("unknown", priority=None), obj("empty", {(1, 0)}, candidates=()),
                       obj("auto", {(2, 0)}, priority=None, auto=7), obj("zero", {(3, 0)}, priority=0, auto=9))
        self.assertEqual(codes(result, "unknown"), {Code.MISSING_SPECIFICITY})
        self.assertEqual(codes(result, "empty"), {Code.NO_CANDIDATES})
        self.assertEqual(outcomes(result)["auto"].effective_specificity, 7)
        self.assertEqual(outcomes(result)["zero"].effective_specificity, 0)

    def test_late_high_priority_does_not_displace_accepted_and_accepted_not_reemitted(self):
        initial = solve(obj("old", priority=0))
        old = outcomes(initial)["old"]
        result = solve(obj("new", priority=999), accepted=(old,), phase="dependent")
        self.assertEqual(tuple(outcomes(result)), ("new",))
        self.assertEqual(codes(result, "new"), {Code.SPATIAL_CONFLICT})
        self.assertEqual(old.candidate_uid, "old/fixed")
        self.assertEqual(solve(accepted=(old,), phase="dependent").results, ())
        self.assertEqual(solve().results, ())

    def test_full_and_partial_materialization_share_the_entire_candidate_universe(self):
        # A winner whose remaining cells lie outside the selected output tile
        # must still participate in placement; tile filtering is downstream.
        world = batch(obj("large", {(0, 0), (20, 0)}, area=100), obj("local", {(0, 0)}, area=1))
        full = resolve_placements(world, ctx=ResolveContext(validate_only=True))
        partial = resolve_placements(world.model_copy(update={"objects": tuple(reversed(world.objects))}),
                                     ctx=ResolveContext(validate_only=True))
        self.assertEqual(full, partial)
        emitted = {item.identity.region_uid: item.footprint.cells & {(0, 0)} for item in partial.results
                   if isinstance(item, ResolvedPlacement)}
        self.assertEqual(emitted, {"large": frozenset({(0, 0)})})
        self.assertEqual(outcomes(full)["large"].original_area, 100)
        with self.assertRaises(TypeError):
            resolve_placements(world, ctx=ResolveContext(partial=True))

    def test_worker_count_and_repeated_invocations_have_no_shared_winners(self):
        source = batch(obj("a", priority=5), obj("b"), obj("free", {(5, 0)}))

        def run(_):
            local = PlacementBatch.model_validate_json(source.model_dump_json())
            return resolve_placements(local, ctx=ResolveContext(validate_only=True))

        baseline = run(0)
        for count in (1, 3):
            with ThreadPoolExecutor(max_workers=count) as workers:
                self.assertTrue(all(result == baseline for result in workers.map(run, range(6))))


class PlacementDependencyTests(unittest.TestCase):
    def test_newly_ready_child_enters_same_priority_queue_immediately(self):
        objects = (obj("parent", priority=100), obj("child", {(1, 0)}, priority=1000,
                   dependencies=(dep("parent"),)), obj("rival", {(1, 0)}, priority=50))
        baseline = solve(*objects)
        for ordering in permutations(objects):
            self.assertEqual(solve(*ordering), baseline)
        self.assertIsInstance(outcomes(baseline)["parent"], ResolvedPlacement)
        self.assertIsInstance(outcomes(baseline)["child"], ResolvedPlacement)
        self.assertEqual(codes(baseline, "rival"), {Code.SPATIAL_CONFLICT})

    def test_high_child_cannot_resolve_before_low_support_or_bypass_failed_support(self):
        result = solve(obj("parent", priority=1), obj("rival", priority=10),
                       obj("child", {(1, 0)}, priority=999, dependencies=(dep("parent"),)),
                       obj("independent", {(4, 0)}))
        self.assertEqual(codes(result, "parent"), {Code.SPATIAL_CONFLICT})
        self.assertEqual(codes(result, "child"), {Code.FAILED_DEPENDENCY})
        self.assertIsInstance(outcomes(result)["independent"], ResolvedPlacement)

    def test_missing_support_fails_dependents_and_does_not_abort_independent_work(self):
        result = solve(obj("missing", dependencies=(dep("not-in-snapshot"),)),
                       obj("descendant", dependencies=(dep("missing"),)), obj("free", {(8, 0)}))
        self.assertEqual(codes(result, "missing"), {Code.MISSING_DEPENDENCY})
        self.assertEqual(codes(result, "descendant"), {Code.FAILED_DEPENDENCY})
        self.assertIsInstance(outcomes(result)["free"], ResolvedPlacement)

    def test_cycles_distinguished_from_downstream_nodes_with_stable_component_uids(self):
        objects = (obj("a", dependencies=(dep("b"),)),
                   obj("b", dependencies=(dep("a"), dep("c"))), obj("c", dependencies=(dep("b"),)))
        baseline = None
        for ordering in permutations(objects):
            result = solve(*ordering, obj("downstream", dependencies=(dep("c"),)), obj("free", {(8, 0)}))
            for uid in ("a", "b", "c"):
                self.assertEqual(codes(result, uid), {Code.DEPENDENCY_CYCLE})
                self.assertEqual(outcomes(result)[uid].diagnostics[0].related_uids, ("a", "b", "c"))
            self.assertEqual(codes(result, "downstream"), {Code.FAILED_DEPENDENCY})
            if baseline is not None:
                self.assertEqual(result, baseline)
            baseline = result

    def test_deep_dependency_failure_propagation_is_iterative(self):
        chain = [obj("node-0", priority=None)]
        chain.extend(obj(f"node-{i}", dependencies=(dep(f"node-{i - 1}"),)) for i in range(1, 1100))
        result = solve(*reversed(chain))
        self.assertEqual(len(result.results), 1100)
        self.assertEqual(codes(result, "node-0"), {Code.MISSING_SPECIFICITY})
        self.assertEqual(codes(result, "node-1099"), {Code.FAILED_DEPENDENCY})


class PlacementDiagnosticsTests(unittest.TestCase):
    def test_dry_coastline_priority_zero_warns_once_for_many_cells_and_alternatives(self):
        coast = obj("coast", priority=999, area=999, mode="semantic", candidates=(
            variant("a", {(0, 0), (1, 0)}), variant("b", {(1, 0), (2, 0)}, preference=1)),
            coastline={"snapshot_uid": "snapshot", "water_presence": "absent", "reason": "pre-carve is dry"})
        occupied = obj("occupied", {(0, 0), (1, 0), (2, 0)}, priority=1)
        world = batch(coast, occupied)
        runtime = ResolveContext.for_import(validate_only=False).child("placement")
        preview = ResolveContext.for_import(validate_only=True).child("placement")
        before = world.model_dump()
        with self.assertLogs("app.application.jsonValidation.resolve", "WARNING") as log:
            ordinary = resolve_placements(world, ctx=runtime)
        with self.assertNoLogs("app.application.jsonValidation.resolve", "WARNING"):
            master = resolve_placements(world, ctx=preview)
        self.assertEqual(ordinary, master)
        self.assertEqual(runtime.errors, [])
        self.assertEqual(len(preview.errors), len(master.diagnostics))
        self.assertEqual(sum(item.code == Code.COASTLINE_PRIORITY_LOWERED for item in master.diagnostics), 1)
        self.assertEqual(sum(Code.COASTLINE_PRIORITY_LOWERED.value in line for line in log.output), 1)
        self.assertEqual(outcomes(master)["coast"].prepared.intent.placement_specificity, 999)
        self.assertEqual(outcomes(master)["coast"].prepared.effective_specificity, 0)
        self.assertEqual(world.model_dump(), before)
        self.assertTrue(all(issue.path[:1] == ("placement",) for issue in preview.errors))
        self.assertTrue(all("world_uid=world" in issue.message and "region_uid=" in issue.message
                            for issue in preview.errors))

    def test_dry_coastline_can_create_water_with_zero_even_when_auto_not_provided(self):
        coast = obj("coast", priority=None, coastline={
            "snapshot_uid": "snapshot", "water_presence": "absent", "reason": "dry snapshot"})
        result = solve(coast)
        self.assertIsInstance(outcomes(result)["coast"], ResolvedPlacement)
        self.assertEqual(outcomes(result)["coast"].effective_specificity, 0)

    def test_unknown_water_is_not_absent_or_a_priority_default(self):
        result = solve(obj("coast", priority=999, coastline={
            "snapshot_uid": "snapshot", "water_presence": "unknown", "reason": "fact not prepared"}))
        self.assertEqual(codes(result, "coast"), {Code.UNKNOWN_COASTLINE_WATER})
        self.assertNotIn(Code.COASTLINE_PRIORITY_LOWERED, [item.code for item in result.diagnostics])

    def test_typed_input_is_revalidated_without_ref_w_or_hidden_default_repairs(self):
        invalid = obj("bad").model_copy(update={"auto_specificity": -1})
        world = batch(obj("good")).model_copy(update={"objects": (invalid,)})
        ctx = ResolveContext.for_import(validate_only=True)
        with self.assertRaises(UnresolvedModelError):
            resolve_placements(world, ctx=ctx)
        self.assertEqual(ctx.errors[0].path, ("objects", 0, "auto_specificity"))
        with patch("app.application.jsonValidation.resolve._reference_issues", side_effect=AssertionError("second REF-W")):
            self.assertIsInstance(outcomes(solve(obj("good")))["good"], ResolvedPlacement)

    def test_missing_authored_priority_presence_is_preserved_when_auto_is_prepared(self):
        raw = obj("auto").intent.model_dump()
        raw.pop("placement_specificity")
        intent = PlacementIntent.model_validate(raw)
        source = obj("auto", auto=4).model_copy(update={"intent": intent})
        result = outcomes(solve(source))["auto"]
        self.assertEqual(result.effective_specificity, 4)
        self.assertIsNone(result.prepared.intent.placement_specificity)
        self.assertNotIn("placement_specificity", result.prepared.intent.model_fields_set)
        self.assertNotIn("placement_specificity", intent.model_fields_set)

    def test_invalid_topology_copy_is_a_shared_validation_error(self):
        ctx = ResolveContext(validate_only=True)
        source = batch(obj("a"), world_topology=topology().model_copy(update={"mode": "invalid"}))
        with self.assertRaises(UnresolvedModelError):
            resolve_placements(source, ctx=ctx)
        self.assertEqual(ctx.errors[0].path, ("topology", "mode"))


if __name__ == "__main__":
    unittest.main()
