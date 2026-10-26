"""P2 geometry: exact world cells, volume relations, clearances and seams."""

import unittest
from unittest.mock import patch

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.worldData.placement import resolve_placements
from app.dataModel.placement import PlacementIssueCode as Code, ResolvedPlacement, UnresolvedPlacement
from app.dataModel.topology import topologyGeometry
from tests.test_placement_resolver import batch, codes, dep, obj, outcomes, overlap, separation, solve, topology, variant


def rect(x0, x1, y0=0, y1=2):
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


class PlacementRelationTests(unittest.TestCase):
    def test_containment_needs_explicit_permitted_overlap(self):
        parent = obj("parent", rect(0, 4), priority=10, z=(0, 5))
        child = obj("child", {(2, 1)}, z=(1, 3), dependencies=(dep("parent", "contained_by"),))
        result = solve(parent, child)
        self.assertEqual(codes(result, "child"), {Code.SPATIAL_CONFLICT})
        embedded = obj("child", {(2, 1)}, z=(1, 3), dependencies=(dep("parent", "contained_by"),),
                       overlaps=(overlap("parent", "embedding"),))
        self.assertIsInstance(outcomes(solve(parent, embedded))["child"], ResolvedPlacement)

    def test_containment_rejects_outside_xy_or_unbounded_child_in_bounded_container(self):
        parent = obj("parent", rect(0, 4), priority=10, z=(0, 5))
        for cells, z in (({(7, 1)}, (1, 3)), ({(2, 1)}, (None, None)), ({(2, 1)}, (4, 6))):
            child = obj("child", cells, z=z, dependencies=(dep("parent", "contained_by"),),
                        overlaps=(overlap("parent", "embedding"),))
            self.assertEqual(codes(solve(parent, child), "child"), {Code.CONSTRAINT_VIOLATION})

    def test_support_requires_full_xy_support_and_explicit_adjacent_z(self):
        parent = obj("support", {(0, 0)}, z=(0, 0))
        valid = obj("child", {(0, 0)}, z=(1, 2), dependencies=(dep("support", "supported_by"),))
        self.assertIsInstance(outcomes(solve(parent, valid))["child"], ResolvedPlacement)
        for cells, z in (({(0, 0)}, (2, 3)), ({(1, 0)}, (1, 2)), ({(0, 0)}, (None, None))):
            child = obj("child", cells, z=z, dependencies=(dep("support", "supported_by"),))
            self.assertEqual(codes(solve(parent, child), "child"), {Code.CONSTRAINT_VIOLATION})
        unlimited = obj("support", {(0, 0)})
        self.assertEqual(codes(solve(unlimited, valid), "child"), {Code.CONSTRAINT_VIOLATION})

    def test_connection_checks_adjacency_and_vertical_gap(self):
        for child_cells, z, valid in (({(1, 0)}, (0, 0), True), ({(3, 0)}, (0, 0), False),
                                     ({(0, 0)}, (1, 1), True), ({(1, 0)}, (3, 3), False)):
            result = solve(obj("parent", z=(0, 0)), obj("child", child_cells, z=z,
                           dependencies=(dep("parent", "connected_to"),)))
            self.assertEqual(isinstance(outcomes(result)["child"], ResolvedPlacement), valid)

    def test_named_coverage_is_symmetric_but_does_not_allow_unrelated_pair(self):
        owner = obj("owner", priority=10, overlaps=(overlap("allowed"),))
        result = solve(owner, obj("allowed", priority=1), obj("unrelated", priority=0))
        self.assertIsInstance(outcomes(result)["allowed"], ResolvedPlacement)
        self.assertEqual(codes(result, "unrelated"), {Code.SPATIAL_CONFLICT})

    def test_embedding_permission_does_not_allow_arbitrary_partial_overlap(self):
        result = solve(obj("left", rect(0, 2), priority=10),
                       obj("right", rect(1, 3), overlaps=(overlap("left", "embedding"),)))
        self.assertEqual(codes(result, "right"), {Code.SPATIAL_CONFLICT})

    def test_shared_wall_or_connection_allows_boundary_only(self):
        for relation in ("shared_boundary", "connection"):
            for right_cells, valid in ((rect(2, 4), True), (rect(1, 3), False)):
                result = solve(obj("left", rect(0, 2), priority=10),
                               obj("right", right_cells, overlaps=(overlap("left", relation),)))
                self.assertEqual(isinstance(outcomes(result)["right"], ResolvedPlacement), valid)

    def test_reserve_not_cancelled_by_permitted_overlap(self):
        result = solve(obj("a", priority=10), obj("b", overlaps=(overlap("a"),),
                       separations=(separation("a"),)))
        self.assertEqual(codes(result, "b"), {Code.CONSTRAINT_VIOLATION})


class PlacementClearanceTests(unittest.TestCase):
    def test_constraints_of_already_placed_owner_apply_to_later_target(self):
        owner = obj("a", priority=10, separations=(separation("b", xy=1),))
        blocked = solve(owner, obj("b", {(1, 0)}))
        self.assertEqual(codes(blocked, "b"), {Code.CONSTRAINT_VIOLATION})
        variants = (variant("near", {(1, 0)}), variant("far", {(2, 0)}, preference=1))
        result = solve(owner, obj("b", mode="semantic", candidates=variants))
        self.assertEqual(outcomes(result)["b"].candidate_uid, "far")

    def test_xy_or_z_reserve_without_combining_independent_rules_into_maxima(self):
        a = obj("a", priority=10, z=(0, 0), separations=(separation("b", xy=1, z=10),))
        b = obj("b", {(2, 0)}, z=(2, 2), separations=(separation("a", xy=10, z=1),))
        self.assertTrue(all(isinstance(item, ResolvedPlacement) for item in solve(a, b).results))
        self.assertEqual(codes(solve(a, obj("b", z=(1, 1))), "b"), {Code.CONSTRAINT_VIOLATION})

    def test_vertical_reserve_counts_empty_inclusive_levels(self):
        parent = obj("a", priority=10, z=(0, 0), separations=(separation("b", z=1),))
        self.assertIsInstance(outcomes(solve(parent, obj("b", z=(2, 2))))["b"], ResolvedPlacement)
        self.assertEqual(codes(solve(parent, obj("b", z=(1, 1))), "b"), {Code.CONSTRAINT_VIOLATION})

    def test_unbounded_z_cannot_hide_overlap_with_high_altitude_object(self):
        result = solve(obj("unbounded", priority=10), obj("high", z=(1000, 1000)))
        self.assertEqual(codes(result, "high"), {Code.SPATIAL_CONFLICT})


class PlacementTopologyTests(unittest.TestCase):
    def test_unrolled_aliases_collide_through_wrapped_and_sphere_seams(self):
        for mode, alias, canonical in (("wrapped", (8, 0), (0, 0)), ("sphere", (0, -1), (4, 0))):
            result = solve(obj("a", {canonical}, priority=10), obj("b", {alias}),
                           world_topology=topology(mode, x_max=7, y_max=3))
            self.assertEqual(codes(result, "b"), {Code.SPATIAL_CONFLICT})
            self.assertEqual(outcomes(result)["b"].prepared.candidates[0].footprint.cells, frozenset({alias}))

    def test_connected_dependency_uses_world_neighbor_at_wrap_and_pole(self):
        for mode, target in (("wrapped", (7, 0)), ("sphere", (4, 0))):
            result = solve(obj("a"), obj("b", {target}, dependencies=(dep("a", "connected_to"),)),
                           world_topology=topology(mode, x_max=7, y_max=3))
            self.assertIsInstance(outcomes(result)["b"], ResolvedPlacement)
        planar = solve(obj("a"), obj("b", {(7, 0)}, dependencies=(dep("a", "connected_to"),)),
                       world_topology=topology("planar", x_max=7, y_max=3))
        self.assertEqual(codes(planar, "b"), {Code.CONSTRAINT_VIOLATION})

    def test_clearance_uses_topology_metric_instead_of_raw_coordinate_distance(self):
        for mode, other in (("wrapped", (7, 0)), ("sphere", (4, 0))):
            with patch.object(topologyGeometry, "dist2", wraps=topologyGeometry.dist2) as metric:
                result = solve(obj("a", priority=10, separations=(separation("b", xy=1),)),
                               obj("b", {other}), world_topology=topology(mode, x_max=7, y_max=3))
                self.assertEqual(codes(result, "b"), {Code.CONSTRAINT_VIOLATION})
                self.assertTrue(metric.called)
        self.assertIsInstance(outcomes(solve(obj("a", priority=10, separations=(separation("b", xy=1),)),
                                            obj("b", {(7, 0)})))["b"], ResolvedPlacement)

    def test_planar_outside_rejects_whole_candidate_without_clipping(self):
        outside = variant("outside", {(0, 0), (-1, 0)})
        fixed = solve(obj("fixed", candidates=(outside,)))
        self.assertEqual(codes(fixed, "fixed"), {Code.CONSTRAINT_VIOLATION})
        semantic = solve(obj("semantic", mode="semantic", candidates=(outside,
                         variant("inside", {(1, 0)}, preference=1))))
        self.assertEqual(outcomes(semantic)["semantic"].candidate_uid, "inside")

    def test_invalid_accepted_snapshot_is_not_silently_dropped(self):
        accepted = ResolvedPlacement(prepared=obj("old", {(-1, 0)}), candidate_uid="old/fixed")
        source = batch(obj("new"), accepted=(accepted,), phase="dependent")
        ctx = ResolveContext(validate_only=True)
        with self.assertRaises(UnresolvedModelError):
            resolve_placements(source, ctx=ctx)
        self.assertEqual(ctx.errors[0].path, ("accepted", "old", "footprint"))


if __name__ == "__main__":
    unittest.main()
