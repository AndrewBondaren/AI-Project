"""P3 W1/W2: declared water joins the shared pass without carve/fill or a private resolver."""

from dataclasses import replace
from itertools import permutations
import unittest

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.worldData.placement import resolve_placements
from app.application.worldData.placement.adapters import (
    WaterPlacementContext, prepare_water_placements, resolved_water_placements,
)
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype
from app.dataModel.placement import (
    PlacementDependency, PlacementIssueCode, PlacementOverlap, PlacementSeparation, ResolvedPlacement, WaterPresence,
)
from tests.test_placement_resolver import batch, obj, topology


def context(mode="planar", *, z=3, auto=None, subtypes=None):
    surface = {(x, y): z for x in range(20) for y in range(12)}
    return WaterPlacementContext("world", "snapshot", topology(mode, x_max=19, y_max=11),
                                 surface, -100, {}, {} if subtypes is None else subtypes,
                                 {} if auto is None else auto, {}, {}, {})


def basin(uid="basin", **changes):
    return dict(location_uid=uid, kind="ocean", floor_z=-20, placement_specificity=2,
                footprint=dict(kind="bbox", x_min=2, x_max=5, y_min=2, y_max=5)) | changes


def coast(uid="coast", *, closed=False, **changes):
    points = [(5, 3), (5, 8)] if not closed else [(2, 2), (6, 2), (6, 6), (2, 6)]
    values = dict(location_uid=uid, kind="sea", closed=closed,
                  path=[dict(x=x, y=y) for x, y in points])
    if closed:
        values["water_side"] = "interior"
    return values | changes


def lake(uid="lake", points=((2, 2), (6, 2), (6, 6), (2, 6)), **changes):
    return dict(location_uid=uid, shoreline=[dict(x=x, y=y) for x, y in points]) | changes


def prepare(*, basins=(), coasts=(), lakes=(), snapshot=None, ctx=None, **policy):
    return prepare_water_placements(
        WorldHydrology(declared_basins=list(basins), declared_coastlines=list(coasts),
                       declared_lakes=list(lakes), **policy),
        snapshot or context(), ctx=ctx or ResolveContext(validate_only=True))


def resolve(preparation, snapshot, *others):
    result = resolve_placements(batch(*preparation.objects, *others, world_topology=snapshot.topology),
                                ctx=ResolveContext(validate_only=True))
    return result, resolved_water_placements(preparation, result)


class WaterBasinAdapterTests(unittest.TestCase):
    def test_resolved_record_preserves_authored_metadata_and_does_not_mutate_heightmap(self):
        snap = context()
        before = dict(snap.surface_z)
        prep = prepare(basins=[basin(liquid="lava", z_water_level=4)], snapshot=snap)
        result, records = resolve(prep, snap)
        self.assertFalse(prep.failures)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual((record.source_uid, record.z_water_level, record.kind, record.liquid),
                         ("basin", 4, "ocean", "lava"))
        self.assertEqual(len(record.footprint_cells), 16)
        self.assertEqual((prep.entries[0].kind, prep.entries[0].liquid), ("ocean", "lava"))
        self.assertEqual(prep.entries[0].source.floor_z, -20)
        self.assertEqual(snap.surface_z, before)
        self.assertIsInstance(result.results[0], ResolvedPlacement)

    def test_explicit_and_default_level_and_priority_policies(self):
        snap = context(auto={"basin": 7})
        prep = prepare(basins=[basin(placement_specificity=None)], snapshot=snap, default_water_level=8)
        _, records = resolve(prep, snap)
        self.assertEqual(records[0].z_water_level, 8)
        self.assertEqual(records[0].placement.effective_specificity, 7)
        prep = prepare(basins=[basin(placement_specificity=None)])
        result, records = resolve(prep, context())
        self.assertFalse(records)
        self.assertEqual(result.diagnostics[0].code, PlacementIssueCode.MISSING_SPECIFICITY)

    def test_planar_outside_is_failure_without_clipping_and_independent_source_continues(self):
        broken = basin("bad", footprint=dict(kind="bbox", x_min=-1, x_max=2, y_min=1, y_max=3))
        prep = prepare(basins=[broken, basin()])
        self.assertEqual([failure.source_uid for failure in prep.failures], ["bad"])
        self.assertIn("clipping", prep.failures[0].issue.message)
        self.assertEqual([entry.source.location_uid for entry in prep.entries], ["basin"])

    def test_basin_is_not_truncated_by_coastline_caps(self):
        prep = prepare(basins=[basin()], default_seas={"max_area_fraction": 0.001})
        self.assertEqual(len(prep.objects[0].candidates[0].footprint.cells), 16)
        self.assertFalse(prep.notices)

    def test_wrapped_and_sphere_footprints_preserve_original_area_and_authored_shape(self):
        shape = dict(kind="bbox", x_min=18, x_max=22, y_min=3, y_max=5)
        for mode in ("wrapped", "sphere"):
            with self.subTest(mode=mode):
                snap = context(mode)
                prep = prepare(basins=[basin(footprint=shape)], snapshot=snap)
                _, records = resolve(prep, snap)
                self.assertEqual(prep.objects[0].original_area, 15.0)
                self.assertEqual(prep.objects[0].intent.shape.x_max, 22)
                self.assertEqual({x for x, y in records[0].footprint_cells}, {18, 19, 0, 1, 2})

    def test_anchor_and_corridor_reuse_spatial_types(self):
        snap = replace(context(), anchors={"anchor": (6, 6)})
        sources = [basin(footprint=dict(kind="anchor_radius", anchor_uid="anchor", radius=2)),
                   basin("corridor", footprint=dict(kind="corridor", path=[[12, 2], [16, 2]], width=2))]
        prep = prepare(basins=sources, snapshot=snap)
        self.assertFalse(prep.failures)
        self.assertEqual(prep.objects[0].intent.shape.anchor_uid, "anchor")
        self.assertIn((6, 6), prep.objects[0].candidates[0].footprint.cells)
        missing = prepare(basins=[sources[0]])
        self.assertIn("not ready", missing.failures[0].issue.message)

    def test_edge_noise_is_deterministic_and_keeps_source_area(self):
        shape = dict(kind="bbox", x_min=1, x_max=10, y_min=1, y_max=10,
                     edge_noise=dict(amplitude=2, scale=3))
        first = prepare(basins=[basin(footprint=shape)])
        self.assertEqual(first, prepare(basins=[basin(footprint=shape)]))
        self.assertEqual(first.objects[0].original_area, 100)
        self.assertLess(len(first.objects[0].candidates[0].footprint.cells), 100)

    def test_invalid_floor_does_not_get_clamped(self):
        prep = prepare(basins=[basin(floor_z=-101), basin("good")])
        self.assertEqual(prep.failures[0].issue.code, "WATER_PLACEMENT_FLOOR")
        self.assertEqual(len(prep.entries), 1)


class WaterCoastlineAdapterTests(unittest.TestCase):
    def test_open_dry_line_creates_candidate_with_zero_and_policy_cap(self):
        snap = context()
        prep = prepare(coasts=[coast()], snapshot=snap, default_seas={"max_area_fraction": 0.025})
        self.assertFalse(prep.failures)
        self.assertLessEqual(len(prep.objects[0].candidates[0].footprint.cells), 6)
        self.assertEqual(prep.notices[0].code, "WATER_PLACEMENT_CAP_REACHED")
        self.assertEqual(prep.objects[0].coastline.water_presence, WaterPresence.ABSENT)
        result, records = resolve(prep, snap)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].placement.effective_specificity, 0)
        self.assertEqual([fact.code for fact in result.diagnostics],
                         [PlacementIssueCode.COASTLINE_PRIORITY_LOWERED])

    def test_present_water_reads_precarve_level_and_missing_auto_stays_unresolved(self):
        snap = context(z=-2)
        prep = prepare(coasts=[coast()], snapshot=snap)
        self.assertEqual(prep.objects[0].coastline.water_presence, WaterPresence.PRESENT)
        result, records = resolve(prep, snap)
        self.assertFalse(records)
        self.assertEqual(result.diagnostics[0].code, PlacementIssueCode.MISSING_SPECIFICITY)
        snap = replace(snap, auto_specificity={"coast": 4})
        prep = prepare(coasts=[coast()], snapshot=snap)
        _, records = resolve(prep, snap)
        self.assertEqual(records[0].placement.effective_specificity, 4)

    def test_hard_extents_apply_to_wet_and_dry_expansion(self):
        for z in (-3, 3):
            with self.subTest(z=z):
                snap = context(z=z, auto={"coast": 1})
                prep = prepare(coasts=[coast()], snapshot=snap,
                               default_seas=dict(max_area_fraction=1, max_extent_x_fraction=0.1,
                                                 max_extent_y_fraction=0.1))
                cells = prep.objects[0].candidates[0].footprint.cells
                self.assertTrue(all(abs(x - 5) <= 2 for x, y in cells))
                self.assertTrue(all(2 <= y <= 9 for x, y in cells))

    def test_ring_interior_exterior_are_disjoint_and_exclude_boundary(self):
        interior = prepare(coasts=[coast(closed=True)])
        exterior = prepare(coasts=[coast(closed=True, water_side="exterior")])
        inside = interior.objects[0].candidates[0].footprint.cells
        outside = exterior.objects[0].candidates[0].footprint.cells
        self.assertEqual(len(inside), 9)
        self.assertTrue(inside.isdisjoint(outside))
        self.assertNotIn((2, 2), inside | outside)
        self.assertEqual(len(inside | outside), 240 - 16)

    def test_ring_through_wrap_and_pole_uses_topology(self):
        for mode, points in (("wrapped", [(18, 3), (22, 3), (22, 7), (18, 7)]),
                             ("sphere", [(2, -2), (6, -2), (6, 2), (2, 2)])):
            with self.subTest(mode=mode):
                snap = context(mode)
                ring = coast(closed=True, path=[dict(x=x, y=y) for x, y in points])
                prep = prepare(coasts=[ring], snapshot=snap)
                self.assertFalse(prep.failures)
                self.assertEqual(len(prep.objects[0].candidates[0].footprint.cells), 9)

    def test_nonseparating_or_invalid_ring_is_explicit_failure(self):
        ring = coast(closed=True, path=[dict(x=x, y=4) for x in (0, 5, 10, 20)])
        prep = prepare(coasts=[ring], snapshot=context("wrapped"))
        self.assertFalse(prep.entries)
        self.assertEqual(prep.failures[0].source_uid, "coast")
        self.assertIn("ring", prep.failures[0].issue.message)

    def test_open_coastline_expands_through_world_seam_and_stays_within_hard_cap(self):
        for mode in ("wrapped", "sphere"):
            with self.subTest(mode=mode):
                snap = context(mode)
                line = coast(path=[dict(x=19, y=3), dict(x=19, y=8)])
                # Put the land mass west of the authored rim; the water side
                # points east and crosses the seam into canonical x=0.
                surface = dict(snap.surface_z)
                surface.update({(x, y): 100 for x in range(12, 19) for y in range(12)})
                snap = replace(snap, surface_z=surface)
                prep = prepare(coasts=[line], snapshot=snap)
                self.assertFalse(prep.failures)
                cells = prep.objects[0].candidates[0].footprint.cells
                self.assertIn(0, {x for x, y in cells})
                self.assertLessEqual(len(cells), 60)


class WaterSharedPassTests(unittest.TestCase):
    def test_explicit_support_and_separation_rules_reach_the_shared_pass(self):
        snap = replace(context(),
                       dependencies={"basin": (PlacementDependency(target_uid="parent", relation="resolved"),)},
                       separations={"basin": (PlacementSeparation(target_uid="parent", min_xy=1, min_z=0),)})
        prep = prepare(basins=[basin()], snapshot=snap)
        result, records = resolve(prep, snap, obj("parent", cells={(6, 3)}, priority=0))
        self.assertFalse(records)
        self.assertEqual(result.results[0].diagnostics[0].code, PlacementIssueCode.CONSTRAINT_VIOLATION)
        result, records = resolve(prep, snap)
        self.assertFalse(records)
        self.assertEqual(result.results[0].diagnostics[0].code, PlacementIssueCode.MISSING_DEPENDENCY)

    def test_named_pair_overlap_is_forwarded_to_shared_resolver_without_a_water_merge_policy(self):
        snap = replace(context(), permitted_overlaps={"a": (PlacementOverlap(target_uid="b", relation="coverage"),)})
        prep = prepare(basins=[basin("a"), basin("b")], snapshot=snap)
        result, records = resolve(prep, snap)
        self.assertEqual([record.source_uid for record in records], ["a", "b"])
        self.assertFalse(result.diagnostics)

    def test_foreign_domain_competes_in_same_pass_and_output_is_permutation_invariant(self):
        snap = context()
        entries = [basin("a"), basin("b")]
        baseline = None
        for sources in permutations(entries):
            prep = prepare(basins=sources, snapshot=snap)
            result, records = resolve(prep, snap, obj("mountain", cells={(3, 3)}, priority=8))
            self.assertFalse(records)
            self.assertEqual(len(result.results), 3)
            if baseline is None:
                baseline = result
            self.assertEqual(result, baseline)

    def test_projection_rejects_wrong_snapshot_missing_source_and_tampered_input(self):
        snap = context()
        prep = prepare(basins=[basin()], snapshot=snap)
        result, _ = resolve(prep, snap)
        wrong = result.model_copy(update={"snapshot_uid": "other"})
        with self.assertRaises(ValueError):
            resolved_water_placements(prep, wrong)
        missing = result.model_copy(update={"results": ()})
        with self.assertRaises(ValueError):
            resolved_water_placements(prep, missing)
        changed = replace(prep, entries=(replace(prep.entries[0], prepared=obj("basin")),))
        with self.assertRaises(ValueError):
            resolved_water_placements(changed, result)

    def test_incomplete_snapshot_and_duplicate_sources_are_input_errors(self):
        snap = context()
        partial = replace(snap, surface_z={(2, 2): 3})
        for case in (dict(basins=[basin()], snapshot=partial),
                     dict(basins=[basin("coast")], coasts=[coast()]),
                     dict(basins=[basin("lake")], lakes=[lake()])):
            with self.subTest(case=case), self.assertRaises(UnresolvedModelError) as failure:
                prepare(**case)
            self.assertEqual(failure.exception.issues[0].path, ("water_placement",))
            self.assertNotIn("source_uid=", failure.exception.issues[0].message)

    def test_runtime_preview_preparation_parity_and_warning_paths(self):
        snap = context()
        arguments = dict(basins=[basin("bad", floor_z=-101)], coasts=[coast()], snapshot=snap)
        runtime = ResolveContext(path_prefix=("master",))
        preview = ResolveContext(validate_only=True, path_prefix=("master",))
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as log:
            actual = prepare(**arguments, ctx=runtime)
        with self.assertNoLogs("app.application.jsonValidation.resolve", level="WARNING"):
            expected = prepare(**arguments, ctx=preview)
        self.assertEqual(actual, expected)
        self.assertFalse(runtime.errors)
        self.assertEqual(preview.errors[0].path, ("master", "water_placement", "bad"))
        self.assertTrue(all("WarningError" in message for message in log.output))


class WaterLakeAdapterTests(unittest.TestCase):
    def test_ring_becomes_record_with_terrain_derived_level(self):
        snap = context(auto={"lake": 1})
        before = dict(snap.surface_z)
        prep = prepare(lakes=[lake()], snapshot=snap)
        self.assertFalse(prep.failures)
        self.assertFalse(prep.notices)
        cells = prep.objects[0].candidates[0].footprint.cells
        self.assertEqual(len(cells), 9)
        self.assertNotIn((2, 2), cells)
        self.assertIn((3, 3), cells)
        self.assertIsNone(prep.entries[0].prepared.intent.placement_specificity)
        self.assertIsNone(prep.entries[0].prepared.intent.shape)
        _, records = resolve(prep, snap)
        record = records[0]
        self.assertEqual((record.kind, record.liquid, record.z_water_level), ("lake", "water", 3))
        self.assertEqual(snap.surface_z, before)

    def test_level_is_the_rim_of_land_not_the_interior(self):
        snap = context(auto={"lake": 1})
        surface = dict(snap.surface_z)
        surface[(2, 4)] = 9
        surface[(3, 3)] = -50
        snap = replace(snap, surface_z=surface)
        prep = prepare(lakes=[lake()], snapshot=snap)
        _, records = resolve(prep, snap)
        self.assertEqual(records[0].z_water_level, 9)

    def test_liquid_passes_through_to_the_record(self):
        snap = context(auto={"lake": 1})
        prep = prepare(lakes=[lake(liquid="lava")], snapshot=snap)
        _, records = resolve(prep, snap)
        self.assertEqual(records[0].liquid, "lava")

    def test_degenerate_shoreline_falls_back_to_contour_with_notice(self):
        for points in (((2, 4), (8, 4)), ((2, 4), (5, 4), (8, 4))):
            with self.subTest(points=points):
                snap = context(auto={"lake": 1})
                prep = prepare(lakes=[lake(points=points)], snapshot=snap)
                self.assertFalse(prep.failures)
                self.assertEqual(prep.notices[0].code, "WATER_PLACEMENT_DEGENERATE_RING")
                cells = prep.objects[0].candidates[0].footprint.cells
                self.assertEqual(cells, {(x, 4) for x in range(2, 9)})
                _, records = resolve(prep, snap)
                self.assertEqual(records[0].kind, "lake")

    def test_subtype_kind_mismatch_is_a_notice_and_never_changes_kind(self):
        snap = context(auto={"lake": 1}, subtypes={"lake": GeographicSubtype.INLAND_SEA})
        prep = prepare(lakes=[lake()], snapshot=snap)
        self.assertEqual(prep.notices[0].code, "WATER_PLACEMENT_KIND_MISMATCH")
        self.assertEqual(prep.entries[0].kind, "lake")
        snap = context(subtypes={"lake": GeographicSubtype.LAKE})
        prep = prepare(lakes=[lake()], snapshot=snap)
        self.assertFalse(prep.notices)
        snap = context(subtypes={"coast": GeographicSubtype.LAKE})
        prep = prepare(coasts=[coast()], snapshot=snap)
        self.assertEqual(prep.notices[0].code, "WATER_PLACEMENT_KIND_MISMATCH")
        self.assertEqual(prep.entries[0].kind, "sea")
        for subtype in (GeographicSubtype.OCEAN, GeographicSubtype.ISLAND):
            with self.subTest(subtype=subtype):
                snap = context(subtypes={"basin": subtype})
                prep = prepare(basins=[basin()], snapshot=snap)
                self.assertFalse(prep.notices)

    def test_floor_below_z_min_is_failure_and_other_sources_continue(self):
        snap = context(z=-98, auto={"lake": 1, "basin": 1})
        prep = prepare(lakes=[lake()], basins=[basin()], snapshot=snap)
        self.assertEqual(prep.failures[0].issue.code, "WATER_PLACEMENT_FLOOR")
        self.assertEqual([entry.source.location_uid for entry in prep.entries], ["basin"])

    def test_too_few_waypoints_is_a_geometry_failure(self):
        for shoreline in ([], [dict(x=2, y=2)]):
            with self.subTest(shoreline=shoreline):
                prep = prepare(lakes=[lake(shoreline=shoreline)])
                self.assertFalse(prep.entries)
                self.assertEqual(prep.failures[0].issue.code, "WATER_PLACEMENT_GEOMETRY")
                self.assertIn("distinct", prep.failures[0].issue.message)

    def test_ring_across_the_wrapped_seam(self):
        snap = context("wrapped", auto={"lake": 1})
        prep = prepare(lakes=[lake(points=((18, 3), (22, 3), (22, 7), (18, 7)))], snapshot=snap)
        self.assertFalse(prep.failures)
        cells = prep.objects[0].candidates[0].footprint.cells
        self.assertEqual(len(cells), 9)
        self.assertEqual({x for x, _ in cells}, {19, 0, 1})

    def test_source_order_permutation_is_deterministic(self):
        snap = context(auto={"lake": 1, "basin": 1})
        sources = [lake(), basin()]
        baseline = None
        for ordered in permutations(sources):
            prep = prepare(basins=[s for s in ordered if "footprint" in s],
                           lakes=[s for s in ordered if "shoreline" in s], snapshot=snap)
            result, records = resolve(prep, snap)
            if baseline is None:
                baseline = (prep, result, records)
            self.assertEqual((prep, result, records), baseline)


if __name__ == "__main__":
    unittest.main()
