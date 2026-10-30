"""One terrain plan supplies ready extents, with no tile/surface-dependent fallback."""

from copy import deepcopy
from dataclasses import dataclass
from unittest import TestCase

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.regions.regionExtent import prepare_terrain_regions, require_terrain_region
from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure as Measure
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.regionShape import AnchorRadiusShape, BboxShape, PolygonShape
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterAnchorInput
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.regions.regionPlanningInput import RegionGeometryInput, TerrainRegionPlanningInput
from app.dataModel.terrain.regions.terrainRegionExtent import RegionExtentIssueCode, TerrainRegionExtent
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan, TerrainRegionsSnapshot
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


@dataclass(frozen=True)
class CapturedWorld:
    world_uid: str = "extent-world"


WORLD = CapturedWorld()


def inputs(*regions, mode=Mode.WRAPPED, fine_span=1, declared=True, anchors=()):
    bounds = WorldBounds(x_min=0, x_max=2, y_min=0, y_max=3)
    return TerrainRegionPlanningInput(snapshot_uid="snapshot", world_region_uid="world-region",
        declared_world_bounds=bounds if declared else None,
        topology=WorldTopology(mode=mode, bounds=bounds), grid=SurfaceGridSettings(fine_span=fine_span, light_side=1),
        regions=tuple(regions), anchors=anchors)


def build(value):
    return prepare_terrain_regions(WORLD, inputs=value)


def claim_ref(world_uid=WORLD.world_uid):
    key = PlanKey.model_validate({"world_uid": world_uid, "scope": WorldPlanScope(),
        "contract_id": "terrain.claim", "schema_version": 1, "algorithm_version": 1,
        "input_fingerprint": b"i" * 32})
    return PlanRef(key=key, output_fingerprint=b"o" * 32)


class ExtentTests(TestCase):
    def test_coarse_to_fine_square_units_and_sphere_normalized_width(self):
        for mode in Mode:
            value = inputs(mode=mode, fine_span=5)
            plan = build(value)
            expected = value.topology.bounds.width * value.topology.bounds.height * 25
            self.assertEqual(plan.snapshot.world_region.generation_area_fine2, expected)
            self.assertEqual(plan.snapshot.world_region.region_uid, "world-region")
            self.assertEqual(TerrainRegionPlan.model_validate_json(plan.model_dump_json()), plan)

    def test_irregular_region_area_and_world_extent_have_different_units_from_placement(self):
        region = RegionGeometryInput(region_uid="triangle", geometry=PolygonShape(vertices=((0, 0), (4, 0), (0, 4))))
        plan = build(inputs(region, fine_span=3))
        self.assertEqual(plan.snapshot.region_for("triangle").generation_area_fine2, 15)
        self.assertEqual(plan.snapshot.world_region.generation_area_fine2, 108)
        self.assertEqual(plan.snapshot.world_uid, WORLD.world_uid)
        self.assertEqual(plan.snapshot.snapshot_uid, "snapshot")

    def test_absent_declared_bounds_never_create_aabb_world_region(self):
        region = RegionGeometryInput(region_uid="authored", geometry=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1))
        plan = build(inputs(region, declared=False))
        self.assertIsNone(plan.snapshot.world_region)
        self.assertEqual(plan.snapshot.region_for("authored").generation_area_fine2, 4)
        self.assertIsNone(plan.snapshot.region_for("world-region"))

    def test_missing_and_mismatched_identity_are_explicit_build_failures(self):
        snapshot = build(inputs()).snapshot
        for world_uid, snapshot_uid, region_uid, expected in (
            (WORLD.world_uid, "snapshot", "missing", RegionExtentIssueCode.MISSING_REGION),
            ("other", "snapshot", "world-region", RegionExtentIssueCode.IDENTITY_MISMATCH),
            (WORLD.world_uid, "other", "world-region", RegionExtentIssueCode.IDENTITY_MISMATCH),
        ):
            with self.assertRaises(PlanBuildFailure) as error:
                require_terrain_region(snapshot, world_uid=world_uid, snapshot_uid=snapshot_uid, region_uid=region_uid)
            self.assertEqual(error.exception.issues[0].code, expected.value)
        self.assertEqual(require_terrain_region(snapshot, world_uid=WORLD.world_uid, snapshot_uid="snapshot",
            region_uid="world-region"), snapshot.world_region)

    def test_ready_anchor_resolves_geometry_and_missing_anchor_is_not_skipped(self):
        region = RegionGeometryInput(region_uid="anchor-region", geometry=AnchorRadiusShape(anchor_uid="anchor", radius=1))
        with self.assertRaises(PlanBuildFailure) as error:
            build(inputs(region))
        self.assertEqual(error.exception.issues[0].code, RegionExtentIssueCode.MISSING_ANCHOR)
        anchor = WaterAnchorInput(source_uid="anchor", position=(1, 1), subtype=None)
        result = build(inputs(region, anchors=(anchor,)))
        self.assertEqual(result.snapshot.region_for("anchor-region").generation_area_fine2, 5)

    def test_claim_geometry_is_ready_canonical_and_uses_its_existing_uid(self):
        claim = RegionCoverage(region_uid="claim", spans=(CoverageSpan(y=0, x0=0, x1=2),))
        value = inputs(RegionGeometryInput(region_uid="claim", geometry=claim, owner_ref=claim_ref()))
        result = build(value)
        self.assertEqual(result.snapshot.region_for("claim").generation_area_fine2, 2)
        with self.assertRaises(ValidationError):
            RegionGeometryInput(region_uid="other", geometry=claim, owner_ref=claim_ref())
        outside = RegionCoverage(region_uid="claim", spans=(CoverageSpan(y=100, x0=0, x1=1),))
        with self.assertRaises(PlanBuildFailure):
            build(inputs(RegionGeometryInput(region_uid="claim", geometry=outside, owner_ref=claim_ref())))

    def test_claim_owner_ref_is_required_and_checked_for_world_identity(self):
        claim = RegionCoverage(region_uid="claim", spans=())
        with self.assertRaises(ValidationError):
            RegionGeometryInput(region_uid="claim", geometry=claim)
        with self.assertRaises(PlanBuildFailure) as error:
            build(inputs(RegionGeometryInput(region_uid="claim", geometry=claim, owner_ref=claim_ref("other-world"))))
        self.assertEqual(error.exception.issues[0].code, RegionExtentIssueCode.IDENTITY_MISMATCH)
        with self.assertRaises(ValidationError):
            RegionGeometryInput(region_uid="shape", geometry=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1), owner_ref=claim_ref())

    def test_region_plan_never_mints_a_replacement_for_world_identity_collision(self):
        region = RegionGeometryInput(region_uid="world-region", geometry=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1))
        with self.assertRaises(PlanBuildFailure) as error:
            build(inputs(region))
        self.assertEqual(error.exception.issues[0].code, RegionExtentIssueCode.INVALID_GEOMETRY)

    def test_complete_plan_does_not_depend_on_materialization_tiles_or_change_inputs(self):
        region = RegionGeometryInput(region_uid="region", geometry=BboxShape(x_min=-1, x_max=4, y_min=0, y_max=2))
        value = inputs(region)
        before = deepcopy(value.model_dump())
        plan = build(value)
        region_coverage = next(c for c in plan.coverages if c.region_uid == "region")
        view_areas = []
        for side in (1, 2, 3):
            requested = RegionCoverage(region_uid="materialization-request", spans=tuple(
                CoverageSpan(y=y, x0=0, x1=side) for y in range(side)))
            clipped = Measure.intersection(region_coverage, requested, region_uid="visible-part")
            view_areas.append(Measure.area(clipped))
            extent = require_terrain_region(plan.snapshot, world_uid=WORLD.world_uid,
                snapshot_uid="snapshot", region_uid="region")
            self.assertEqual(extent.generation_area_fine2, 9)
        self.assertEqual(view_areas, [1, 4, 9])
        self.assertEqual(value.model_dump(), before)
        self.assertNotIn("surface_z", TerrainRegionPlanningInput.model_fields)
        self.assertNotIn("tiles", TerrainRegionPlanningInput.model_fields)

    def test_empty_plan_and_empty_authored_region_are_valid(self):
        value = inputs(mode=Mode.PLANAR, declared=False)
        self.assertEqual(build(value).coverages, ())
        empty = RegionGeometryInput(region_uid="empty", geometry=BboxShape(x_min=100, x_max=102, y_min=100, y_max=102))
        self.assertEqual(build(inputs(empty, mode=Mode.PLANAR)).snapshot.region_for("empty").generation_area_fine2, 0)

    def test_duplicate_ids_wrong_extents_and_nonpositive_world_area_are_rejected(self):
        extent = TerrainRegionExtent(region_uid="region", generation_area_fine2=0)
        with self.assertRaises(ValidationError):
            TerrainRegionsSnapshot(world_uid="world", snapshot_uid="snap", world_region=extent, regions=())
        with self.assertRaises(ValidationError):
            TerrainRegionsSnapshot(world_uid="world", snapshot_uid="snap", world_region=None, regions=(extent, extent))
        snapshot = TerrainRegionsSnapshot(world_uid="world", snapshot_uid="snap", world_region=None, regions=(extent,))
        with self.assertRaises(ValidationError):
            TerrainRegionPlan(snapshot=snapshot, coverages=())
        for area in (True, -1, 1.0):
            with self.assertRaises(ValidationError):
                TerrainRegionExtent(region_uid="region", generation_area_fine2=area)

    def test_input_world_extent_mismatch_and_duplicate_sources_are_rejected(self):
        value = inputs()
        with self.assertRaises(ValidationError):
            TerrainRegionPlanningInput.model_validate(value.model_dump() | {
                "declared_world_bounds": WorldBounds(x_min=0, x_max=7, y_min=0, y_max=3)})
        region = RegionGeometryInput(region_uid="duplicate", geometry=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1))
        with self.assertRaises(ValidationError):
            inputs(region, region)
        forged = value.topology.model_copy(update={"bounds": value.topology.bounds.model_copy(update={"x_max": 1.5})})
        with self.assertRaises(ValidationError):
            TerrainRegionPlanningInput.model_validate(value.model_dump() | {"topology": forged})


    def test_phase_and_world_region_identities_are_required_in_frozen_input(self):
        value = inputs()
        for name in ("snapshot_uid", "world_region_uid"):
            values = {field: getattr(value, field) for field in type(value).model_fields}
            values.pop(name)
            with self.subTest(field=name), self.assertRaises(ValidationError):
                type(value).model_validate(values)
            with self.assertRaises(ValidationError):
                type(value).model_validate(value.model_dump() | {name: 123})
