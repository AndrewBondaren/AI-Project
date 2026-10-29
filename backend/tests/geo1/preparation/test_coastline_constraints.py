"""Captured source constraints precede one common field selection; no water or Z writes."""

from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.preparation.coastlineConstraintPreparer import CoastlineConstraintPreparer
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.waterSide import WaterSide
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource
from app.dataModel.terrain.designedWater.geometry.waterDesignConstraints import WaterDesignConstraints
from app.dataModel.terrain.designedWater.input import NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode as Code
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.topology.fineTopology import fine_topology
from tests.geo1.authored.fixtures import request
from tests.geo1.authored.test_geometry import ring
from tests.geo1.contracts.strategies.fixtures import inputs, draft_for


def case(*, closed=True, side=WaterSide.INTERIOR, mode=Mode.PLANAR, allocated=None, strategy=Strategy.CONTINENTAL_NOISE):
    source = CoastlineWaterSource(value=DeclaredCoastline(location_uid="source", kind=BasinKind.SEA,
        path=ring() if closed else ring()[:2], closed=closed, water_side=side if closed else None))
    req = request(source, mode=mode)
    constraints = CoastlineConstraintPreparer().prepare(req)
    base = inputs(strategy)
    span = req.grid.fine_span
    bounds = req.topology.bounds
    area = bounds.width * bounds.height * span**2
    coverage = RegionCoverage(region_uid="region", spans=tuple(CoverageSpan(y=y,
        x0=bounds.x_min*span, x1=(bounds.x_max+1)*span)
        for y in range(bounds.y_min*span, (bounds.y_max+1)*span)))
    allocation = allocated if allocated is not None else len(constraints.required_cells)*span**2
    model = {Strategy.CONTINENTAL_NOISE: NoiseWaterDesignInput, Strategy.PLATE: PlateWaterDesignInput,
             Strategy.PLATE_NOISE: PlateNoiseWaterDesignInput}[strategy]
    value = model[CoastlineWaterSource](source=source, metadata=base.metadata.model_copy(update={"source_kind":source.kind}),
        context=base.context.model_copy(update={"autoresolve":True}),
        region=base.region.model_copy(update={"generation_area_fine2":area}),
        budget=base.budget.model_copy(update={"requested_fine2":area,"allocated_fine2":allocation}),
        seed_root=req.seed_root, z_min=req.z_min, topology=req.topology, grid=req.grid, pre_hydrology=req.pre_hydrology,
        region_coverage=coverage, constraints=constraints,
        field_policy=base.field_policy.model_copy(update={"seed_root":req.seed_root,
            "topology":fine_topology(req.topology, span)}))
    return req, value, draft_for(value)


def prepare(value, draft):
    return DesignedWaterPlacementPreparer().prepare(value, draft, selection_policy=WaterFieldSelectionPolicy())


class CoastlineConstraintsTests(TestCase):
    def test_closed_interior_exterior_masks_reuse_existing_geometry(self):
        for side in (WaterSide.INTERIOR, WaterSide.EXTERIOR):
            req, value, draft = case(side=side)
            self.assertEqual(value.constraints.allowed_cells, prepare_authored_water_geometry(req).footprints[0])
            result = prepare(value, draft)
            self.assertEqual(result.candidates[0].footprint.cells, value.constraints.required_cells)
            self.assertEqual(result.metadata.source_uid, req.source.value.location_uid)
            self.assertEqual(result.metadata.source_kind, req.source.kind)

    def test_open_source_works_on_dry_terrain_without_water_support(self):
        req, value, draft = case(closed=False)
        before = req.pre_hydrology.model_dump_json()
        self.assertTrue(all(z > value.metadata.level for _,z in req.pre_hydrology.payload.surface_z))
        result = prepare(value, draft)
        self.assertTrue(result.candidates[0].footprint.cells)
        self.assertEqual(req.pre_hydrology.model_dump_json(), before)
        self.assertTrue(value.constraints.required_cells <= result.candidates[0].footprint.cells)

    def test_all_three_algorithms_use_same_constraint_consumer(self):
        results = []
        for strategy in (Strategy.CONTINENTAL_NOISE, Strategy.PLATE, Strategy.PLATE_NOISE):
            _, value, draft = case(strategy=strategy)
            results.append(prepare(value, draft).candidates[0].footprint.cells)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_land_side_high_scores_cannot_displace_required_strip(self):
        _, value, draft = case()
        required = value.constraints.required_cells
        self.assertLess(len(required), len(value.constraints.allowed_cells))
        samples = tuple((coord, 1.0 if (coord.gx,coord.gy) in required else -1.0)
                        for coord,_ in draft.field.samples)
        changed = type(draft).model_validate(draft.model_copy(update={"field":draft.field.model_copy(update={"samples":samples})}))
        self.assertEqual(prepare(value, changed).candidates[0].footprint.cells, required)

    def test_extra_budget_uses_only_allowed_remaining_cells(self):
        _, value, draft = case(allocated=36)
        result = prepare(value, draft)
        cells = result.candidates[0].footprint.cells
        self.assertEqual(cells, value.constraints.allowed_cells)
        self.assertEqual(len(cells)*value.grid.fine_span**2, 36)

    def test_insufficient_required_budget_is_conflict_not_truncated_line(self):
        for allocated in (0,4,31):
            _, value, draft = case(allocated=allocated)
            with self.assertRaises(PlanBuildFailure) as caught:
                prepare(value, draft)
            self.assertEqual(caught.exception.issues[0].code, Code.CONSTRAINT_CONFLICT.value)

    def test_partial_region_cannot_remove_one_required_cell(self):
        _, value, draft = case()
        x,y = min(value.constraints.required_cells)
        x,y = x*value.grid.fine_span, y*value.grid.fine_span
        spans = []
        for span in value.region_coverage.spans:
            if span.y != y:
                spans.append(span)
            else:
                if span.x0 < x: spans.append(CoverageSpan(y=y,x0=span.x0,x1=x))
                if x+1 < span.x1: spans.append(CoverageSpan(y=y,x0=x+1,x1=span.x1))
        coverage = RegionCoverage(region_uid=value.region.region_uid,spans=tuple(spans))
        area = value.region.generation_area_fine2-1
        changed = type(value).model_validate(value.model_copy(update={"region_coverage":coverage,
            "region":value.region.model_copy(update={"generation_area_fine2":area}),
            "budget":value.budget.model_copy(update={"requested_fine2":area})}))
        with self.assertRaises(PlanBuildFailure) as caught:
            prepare(changed, draft)
        self.assertEqual(caught.exception.issues[0].code, Code.CONSTRAINT_CONFLICT.value)

    def test_caps_and_coverage_shortfall_notices_both_survive(self):
        req, value, draft = case(closed=False, allocated=200)
        limited = type(req).model_validate(req.model_copy(update={"seas":req.seas.model_copy(update={"max_area_fraction":0.15})}))
        constraints = CoastlineConstraintPreparer().prepare(limited)
        value = type(value).model_validate(value.model_copy(update={"constraints":constraints}))
        result = prepare(value, draft)
        codes = {notice.code for notice in result.notices}
        self.assertIn("WATER_PLACEMENT_CAP_REACHED", codes)
        self.assertIn(Code.COVERAGE_SHORTFALL.value, codes)
        self.assertEqual(result.candidates[0].footprint.cells,value.constraints.allowed_cells)

    def test_source_path_ref_and_scale_are_bound_to_constraints(self):
        _, value, _ = case()
        constraints = value.constraints
        changed_path = constraints.source.value.model_copy(update={"path":tuple(reversed(constraints.source.value.path))})
        for update in ({"source":constraints.source.model_copy(update={"value":changed_path})},
                       {"pre_hydrology_ref":constraints.pre_hydrology_ref.model_copy(update={"output_fingerprint":b"x"*32})},
                       {"grid":constraints.grid.model_copy(update={"fine_span":3})},
                       {"allowed_cells":constraints.allowed_cells|{(100,100)}}):
            with self.assertRaises(ValidationError):
                type(value).model_validate(value.model_copy(update={"constraints":constraints.model_copy(update=update)}))

    def test_missing_constraints_is_not_unconstrained_procedural_coastline(self):
        _, value, _ = case()
        with self.assertRaises(ValidationError):
            type(value).model_validate(value.model_copy(update={"constraints":None}))

    def test_result_is_strict_immutable_and_round_trips(self):
        _, value, _ = case()
        constraints = value.constraints
        self.assertEqual(WaterDesignConstraints.model_validate_json(constraints.model_dump_json()),constraints)
        for update in ({"required_cells":frozenset({(100,100)})}, {"required_cells":frozenset()},
                       {"allowed_cells":list(constraints.allowed_cells)}):
            with self.assertRaises(ValidationError):
                WaterDesignConstraints.model_validate(constraints.model_copy(update=update))
        with self.assertRaises(ValidationError):
            constraints.allowed_cells = frozenset()

    def test_geometry_is_computed_once_and_not_resampled_by_common_preparer(self):
        req, value, draft = case()
        target = "app.application.worldData.generators.terrain.designedWater.preparation.coastlineConstraintPreparer.prepare_authored_water_geometry"
        with patch(target, wraps=prepare_authored_water_geometry) as geometry:
            CoastlineConstraintPreparer().prepare(req)
            self.assertEqual(geometry.call_count,1)
        with patch(target, side_effect=AssertionError("resampled")):
            prepare(value,draft)

    def test_no_policy_execution_during_constraint_collection(self):
        from app.application.policy.policyResolver import PolicyResolver
        with patch.object(PolicyResolver,"resolve",side_effect=AssertionError("policy")):
            case()

    def test_wrapped_and_sphere_constraints_keep_seam_path_and_canonical_cells(self):
        for mode in (Mode.WRAPPED, Mode.SPHERE):
            req, _, _ = case(mode=mode)
            source = req.source.value.model_copy(update={"path":tuple(
                point.model_copy(update={"x":point.x-8}) for point in req.source.value.path)})
            changed = type(req).model_validate(req.model_copy(update={"source":CoastlineWaterSource(value=source)}))
            constraints = CoastlineConstraintPreparer().prepare(changed)
            self.assertEqual(constraints.source.value.path,source.path)
            self.assertTrue(all(changed.topology.canonicalize(*c)==c for c in constraints.allowed_cells))
            self.assertTrue({0,9} <= {x for x,_ in constraints.allowed_cells})

    def test_cap_that_cannot_cover_authored_line_is_explicit_conflict(self):
        req, _, _ = case(closed=False)
        tiny = req.seas.model_copy(update={"max_area_fraction":0.01})
        with self.assertRaises(PlanBuildFailure) as caught:
            CoastlineConstraintPreparer().prepare(type(req).model_validate(req.model_copy(update={"seas":tiny})))
        self.assertEqual(caught.exception.issues[0].code,Code.CONSTRAINT_CONFLICT.value)

    def test_rejects_non_coastline_and_raw_geometry_requests(self):
        with self.assertRaises(ValueError):
            CoastlineConstraintPreparer().prepare(request())
        with self.assertRaises(TypeError):
            CoastlineConstraintPreparer().prepare({})
