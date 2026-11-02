"""Contract admission only: these fixtures do not publish or solve water."""

from unittest import TestCase

from pydantic import ValidationError

from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.query.source import CanonicalOpenWaterSource, WaterMembershipRun, WaterSourceIssueCode
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


def bed():
    return FineSurfaceWindow(
        coverage=RegionCoverage(region_uid="observed", spans=(CoverageSpan(y=-1, x0=0, x1=4),)),
        topology=WorldTopology(mode=WorldTopologyMode.PLANAR,
                               bounds=WorldBounds(x_min=0, x_max=3, y_min=-1, y_max=-1)),
        surface_z=tuple(((FineX(x), FineY(-1)), FineZ(z)) for x, z in enumerate((-3, -1, 2, -4))),
        protected_cells=frozenset({(0, -1)}))


def body(uid="body", parent=None, level=0):
    return WaterBody(water_body_uid=uid, kind=BasinKind.LAKE, declared_level=-1,
                     z_water_level=level, parent_system_uid=parent)


def run(x0=0, x1=2, uid="body", y=-1):
    return WaterMembershipRun(y=y, x0=x0, x1=x1, body_uid=uid)


def values():
    return dict(space=CoordinateSpace.WORLD_FINE_GRID, bed=bed(), z_min=-5, z_max=4,
                wet_runs=(run(),), bodies=(body(),), unions=(),
                source_mapping=SourceBodyMapping(entries=(SourceBodyMappingEntry(
                    source_uid="authored", body_uids=("body",)),)), shore_rows=())


def source(**changes):
    data = values()
    data.update(changes)
    return CanonicalOpenWaterSource(**data)


def union(uid, members=("body",), children=(), parent=None, level=0):
    return PhysicalWaterUnion(water_system_uid=uid, member_uids=members,
                              child_system_uids=children, parent_system_uid=parent, z_water_level=level)


class SourceModelTests(TestCase):
    def test_known_dry_retains_explicit_observation_and_empty_source_mapping(self):
        mapping = SourceBodyMapping(entries=(SourceBodyMappingEntry(source_uid="dry", body_uids=()),))
        data = source(wet_runs=(), bodies=(), source_mapping=mapping)
        self.assertEqual(data.bed.coverage.spans[0].x1, 4)
        self.assertEqual(data.source_mapping, mapping)
        self.assertEqual(data.wet_runs, ())

    def test_exact_negative_bed_and_no_fill_of_isolated_low_dry_cell(self):
        data = source()
        self.assertEqual(data.bed.surface_z[0][1], -3)
        self.assertEqual(data.bodies[0].z_water_level, 0)
        self.assertEqual(data.wet_runs, (run(),))
        self.assertLess(dict(data.bed.surface_z)[(3, -1)], data.bodies[0].z_water_level)
        self.assertEqual(data.wet_runs[0].x1, 2)  # The reader/validator must not flood cell 3.
        self.assertEqual(CanonicalOpenWaterSource.model_validate(data), data)

    def test_frozen_and_no_field_defaults(self):
        for record in (source(), run()):
            with self.subTest(model=type(record).__name__):
                self.assertTrue(all(field.is_required() for field in type(record).model_fields.values()))
                with self.assertRaises(ValidationError):
                    record.space = CoordinateSpace.WORLD_SURFACE_GRID

    def test_rejects_run_coercion_and_invalid_intervals(self):
        for change in ({"x0": True}, {"x1": "2"}, {"y": -1.0}, {"x1": 0},
                       {"x1": -1}, {"body_uid": " "}, {"extra": 1}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                WaterMembershipRun.model_validate(dict(y=-1, x0=0, x1=2, body_uid="body") | change)

    def test_rejects_source_scalar_collection_and_record_coercion(self):
        for change in ({"space": "world_fine_grid"}, {"space": CoordinateSpace.WORLD_SURFACE_GRID},
                       {"z_min": False}, {"z_max": "4"}, {"z_min": -5.0}, {"bodies": [body()]},
                       {"wet_runs": [run()]}, {"bed": bed().model_dump()},
                       {"bodies": (body().model_dump(),)}, {"source_mapping": {"entries": ()}}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                source(**change)

    def test_revalidates_forged_outer_and_nested_records(self):
        cases = [source().model_copy(update={"z_min": True}),
                 source().model_copy(update={"wet_runs": (run().model_copy(update={"x0": -1}),)}),
                 source().model_copy(update={"bed": bed().model_copy(update={"surface_z": ()})}),
                 source().model_copy(update={"bodies": (body().model_copy(update={"z_water_level": True}),)}),
                 source().model_copy(update={"source_mapping": SourceBodyMapping.model_construct(
                     entries=(SourceBodyMappingEntry.model_construct(source_uid="s", body_uids=("missing",)),))}),
                 CanonicalOpenWaterSource.model_construct(**(values() | {"z_max": "4"}))]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                CanonicalOpenWaterSource.model_validate(data)

    def test_legacy_enum_and_integer_normalization_cannot_repair_forged_facts(self):
        shore = MapCellHydrology.shore(HydrologyShoreKind.LAKE)
        cases = [{"bodies": (body().model_copy(update={"kind": "lake"}),)},
                 {"unions": (union("u").model_copy(update={"z_water_level": True}),)},
                 {"shore_rows": (((2, -1), shore.model_copy(update={"shore_kind": "lake"})),)},
                 {"shore_rows": (((2, -1), shore.model_copy(update={"deepening_index": False})),)}]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                source(**change)

    def test_missing_and_extra_constructed_fields_cannot_be_restored(self):
        incomplete = WaterBody.model_construct(water_body_uid="body", kind=BasinKind.LAKE,
                                              declared_level=0, z_water_level=0)
        del incomplete.__dict__["liquid"]
        with self.assertRaisesRegex(ValidationError, "missing or extra"):
            source(bodies=(incomplete,))
        with self.assertRaisesRegex(ValidationError, "missing or extra"):
            source(wet_runs=(run().model_copy(update={"extra": 1}),))

    def test_ready_topology_is_checked_before_legacy_normalization(self):
        topology = bed().topology
        bad_bounds = [topology.bounds.model_copy(update={"x_min": True}),
                      topology.bounds.model_copy(update={"x_max": "3"}),
                      topology.bounds.model_copy(update={"x_max": -1})]
        frames = [topology.model_copy(update={"bounds": bounds}) for bounds in bad_bounds]
        frames += [topology.model_copy(update={"mode": "planar"}),
                   topology.model_copy(update={"bounds": topology.bounds.model_dump()}),
                   topology.model_copy(update={"mode": WorldTopologyMode.SPHERE,
                                               "bounds": topology.bounds.model_copy(update={"x_max": 2})})]
        for frame in frames:
            with self.subTest(frame=frame), self.assertRaises(ValidationError):
                source(bed=bed().model_copy(update={"topology": frame}))

    def test_valid_wrapped_and_sphere_frames_preserve_exact_bounds(self):
        for mode in (WorldTopologyMode.WRAPPED, WorldTopologyMode.SPHERE):
            frame = WorldTopology(mode=mode, bounds=bed().topology.bounds)
            data = source(bed=bed().model_copy(update={"topology": frame}))
            self.assertEqual(data.bed.topology, frame)

    def test_bed_coverage_coordinates_and_protection_are_revalidated(self):
        window = bed()
        for change in ({"surface_z": window.surface_z[:-1]},
                       {"surface_z": (((True, -1), -3), *window.surface_z[1:])},
                       {"protected_cells": frozenset({(8, -1)})},
                       {"coverage": window.coverage.model_copy(update={"spans": (
                           window.coverage.spans[0].model_copy(update={"x1": True}),)})}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                source(bed=window.model_copy(update=change))

    def test_vertical_scope_and_wet_equality_are_rejected(self):
        cases = [({"z_min": 5}, "z_min <= z_max"), ({"z_min": -2}, "bed exceeds"),
                 ({"bodies": (body(level=5),)}, "body level exceeds"),
                 ({"bodies": (body(level=-1),)}, "bed_z < effective level")]
        for change, message in cases:
            with self.subTest(change=change), self.assertRaisesRegex(ValidationError, message):
                source(**change)

    def test_run_coverage_order_overlap_and_merge(self):
        for runs, message in [((run(-1, 1),), "outside observed"), ((run(3, 5),), "outside observed"),
                              ((run(y=0),), "outside observed"), ((run(uid="missing"),), "body is missing"),
                              ((run(1, 2), run(0, 1)), "sorted, disjoint"),
                              ((run(), run(1, 2)), "sorted, disjoint"),
                              ((run(0, 1), run(1, 2)), "adjacent runs merged")]:
            with self.subTest(runs=runs), self.assertRaisesRegex(ValidationError, message):
                source(wet_runs=runs)
        data = source(wet_runs=(run(0, 1), run(1, 2, uid="other")), bodies=(body(), body("other")))
        self.assertEqual(len(data.wet_runs), 2)

    def test_identity_and_mapping_checks(self):
        for change, message in [({"bodies": (body(), body())}, "sorted and unique"),
                                ({"bodies": (body("z"), body())}, "sorted and unique"),
                                ({"bodies": (body(parent="missing"),)}, "parent union is missing"),
                                ({"source_mapping": SourceBodyMapping(entries=(SourceBodyMappingEntry(
                                    source_uid="s", body_uids=("missing",)),))}, "mapping body is missing")]:
            with self.subTest(change=change), self.assertRaisesRegex(ValidationError, message):
                source(**change)

    def test_nested_union_members_and_effective_levels(self):
        data = source(bodies=(body(parent="inner"),),
                      unions=(union("inner", parent="outer"), union("outer", children=("inner",))))
        self.assertEqual(data.unions[1].member_uids, ("body",))
        self.assertEqual(data.bodies[0].declared_level, -1)  # Own level need not equal effective level.

    def test_union_reference_cycle_and_consistency_failures(self):
        cases = [((union("u", members=("missing",)),), body(), "member body is missing"),
                 ((union("u", children=("missing",)),), body(), "child union is missing"),
                 ((union("u", parent="missing"),), body(), "union parent is missing"),
                 ((union("u", parent="u", children=("u",)),), body(parent="u"), "union cycle"),
                 ((union("a", parent="b", children=("b",)), union("b", parent="a", children=("a",))),
                  body(parent="a"), "union cycle"),
                 ((union("a"), union("b", parent="c", children=("c",)),
                   union("c", parent="b", children=("b",))), body(parent="b"), "union cycle"),
                 ((union("inner", parent="outer"), union("outer")), body(parent="inner"), "parent/child"),
                 ((union("u", level=1),), body(parent="u"), "effective level"),
                 ((union("u", level=5),), body(parent="u"), "union level exceeds"),
                 ((union("u"), union("u")), body(parent="u"), "sorted and unique"),
                 ((union("u"),), body(), "ancestry/effective level")]
        for unions, member, message in cases:
            with self.subTest(unions=unions), self.assertRaisesRegex(ValidationError, message):
                source(unions=unions, bodies=(member,))

    def test_union_ancestor_levels_and_member_closure(self):
        with self.assertRaisesRegex(ValidationError, "same effective level"):
            source(bodies=(body(parent="inner"),),
                   unions=(union("inner", parent="outer"), union("outer", children=("inner",), level=1)))
        with self.assertRaisesRegex(ValidationError, "child members must belong"):
            source(bodies=(body(parent="inner"), body("other", parent="outer")),
                   unions=(union("inner", parent="outer"),
                           union("outer", members=("other",), children=("inner",))))

    def test_shore_is_observed_dry_metadata(self):
        shore = MapCellHydrology.shore(HydrologyShoreKind.LAKE, water_body_uid="body").with_water_level(0)
        self.assertEqual(source(shore_rows=(((2, -1), shore),)).shore_rows[0][1].role, HydrologyCellRole.SHORE)
        for rows, message in [((((8, -1), shore),), "observed"), ((((0, -1), shore),), "outside wet"),
                              ((((2, -1), shore), ((2, -1), shore)), "sorted and unique"),
                              ((((2, -1), shore.model_copy(update={"role": HydrologyCellRole.LAKE})),), "SHORE"),
                              ((((2, -1), shore.model_copy(update={"liquid_candidate": True})),), "SHORE"),
                              ((((2, -1), shore.model_copy(update={"water_body_uid": "missing"})),), "shore body"),
                              ((((2, -1), shore.with_water_level(1)),), "disagrees")]:
            with self.subTest(rows=rows), self.assertRaisesRegex(ValidationError, message):
                source(shore_rows=rows)

    def test_issue_code_values_are_the_frozen_contract(self):
        self.assertEqual(tuple(code.value for code in WaterSourceIssueCode), (
            "water_source_invalid_frame", "water_source_revision_mismatch", "water_source_incomplete",
            "water_source_invalid_fact", "water_source_resource_limit"))
