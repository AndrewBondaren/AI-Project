"""Shared caps, exact rounding and typed inputs without spatial ownership."""

from decimal import localcontext
from itertools import permutations
from unittest import TestCase

from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext, WaterGenerationContext
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest, WaterCoverageBudget
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.validation.immutableValue import validate_immutable


def context(fraction=0.6, strategy=Strategy.CONTINENTAL_NOISE):
    return ResolvedWaterGenerationContext(level=Scope.WORLD,
        provenance=tuple((name, (Scope.WORLD, name)) for name in ("autoresolve", "strategy", "water_fraction")),
        water_fraction=fraction, autoresolve=False, strategy=strategy)


def request(uid, area=100, fraction=1.0, region="region"):
    return BodyCoverageRequest(source_uid=uid, generation_region_uid=region,
        generation_area_fine2=area, target_fraction=fraction)


class WaterBudgetTests(TestCase):
    def calculate(self, requests=(), fraction=0.6, area=100, authored=0, available=None, strategy=Strategy.CONTINENTAL_NOISE):
        return WaterCoverageBudgetPolicy().calculate(
            TerrainRegionExtent(region_uid="world-region", generation_area_fine2=area), context(fraction, strategy), requests,
            authored_union_fine2=authored, available_auto_area_fine2=area - authored if available is None else available)

    def test_zero_sixty_and_hundred_percent_share_one_world_target(self):
        for fraction, target in ((0.0, 0), (0.6, 60), (1.0, 100)):
            budget = self.calculate((request("a"), request("b")), fraction=fraction)
            self.assertEqual(budget.target_fine2, target)
            self.assertEqual(sum(a.allocated_fine2 for a in budget.allocations), target)
            self.assertEqual([a.allocated_fine2 for a in budget.allocations], [target // 2] * 2)

    def test_authored_above_target_is_preserved_without_negative_residual(self):
        budget = self.calculate((request("a"),), authored=80)
        self.assertEqual((budget.target_fine2, budget.authored_union_fine2, budget.residual_fine2), (60, 80, 0))
        self.assertEqual(budget.allocations[0].allocated_fine2, 0)

    def test_available_union_caps_overlap_once(self):
        def coverage(uid, start, end):
            return RegionCoverage(region_uid=uid, spans=(CoverageSpan(y=0, x0=start, x1=end),))

        # Geometry is measured by its existing owner, never by the water policy.
        authored = RegionCoverageMeasure.union((coverage("a", 0, 30), coverage("b", 20, 50)), region_uid="authored")
        auto = RegionCoverageMeasure.union((coverage("c", 40, 90), coverage("d", 60, 100)), region_uid="auto")
        available = RegionCoverageMeasure.subtract(auto, authored, region_uid="available")
        budget = self.calculate((request("c", 50, region="c"), request("d", 40, region="d")),
            authored=RegionCoverageMeasure.area(authored), available=RegionCoverageMeasure.area(available))
        self.assertEqual(budget.authored_union_fine2, 50)
        self.assertEqual(budget.residual_fine2, 10)
        self.assertEqual([a.allocated_fine2 for a in budget.allocations], [6, 4])

    def test_available_auto_area_is_global_cap_not_per_body_quota(self):
        budget = self.calculate((request("a"), request("b")), available=7)
        self.assertEqual(budget.residual_fine2, 60)
        self.assertEqual([a.allocated_fine2 for a in budget.allocations], [4, 3])

    def test_largest_remainder_is_proportional_and_bounded_by_requests(self):
        requests = (request("a", 10, region="a"), request("b", 20, region="b"), request("c", 30, region="c"))
        budget = self.calculate(requests, available=16)
        self.assertEqual([a.allocated_fine2 for a in budget.allocations], [3, 5, 8])
        budget = self.calculate(requests, fraction=1.0)
        self.assertEqual([a.allocated_fine2 for a in budget.allocations], [10, 20, 30])
        self.assertEqual(budget.residual_fine2, 100)

    def test_ties_and_output_order_are_uid_deterministic(self):
        requests = tuple(request(uid, 1) for uid in ("c", "b", "a"))
        expected = self.calculate(requests, available=2)
        self.assertEqual([(a.source_uid, a.allocated_fine2) for a in expected.allocations], [("a", 1), ("b", 1), ("c", 0)])
        for order in permutations(requests):
            self.assertEqual(self.calculate(order, available=2), expected)

    def test_zero_empty_and_zero_area_requests_do_not_gain_artificial_weight(self):
        for requests in ((), (request("a", fraction=0.0),), (request("a", 0, region="empty"), request("b", fraction=0.0))):
            budget = self.calculate(requests)
            self.assertEqual(budget.residual_fine2, 60)
            self.assertTrue(all(a.allocated_fine2 == 0 for a in budget.allocations))
        budget = self.calculate((request("zero", fraction=0.0), request("positive")), available=1)
        self.assertEqual([(a.source_uid, a.allocated_fine2) for a in budget.allocations], [("positive", 1), ("zero", 0)])
        self.assertEqual(self.calculate((request("a", 0),), area=0).target_fine2, 0)

    def test_decimal_half_up_applies_to_target_and_body_requests(self):
        for fraction, expected in ((0.145, 15), (0.005, 1), (0.0049, 0)):
            budget = self.calculate((request("a", fraction=fraction),), fraction=fraction)
            self.assertEqual(budget.target_fine2, expected)
            self.assertEqual(budget.allocations[0].requested_fine2, expected)
            self.assertEqual(budget.allocations[0].allocated_fine2, expected)

    def test_exact_large_areas_are_independent_of_decimal_process_precision(self):
        area = 10 ** 80 + 51
        with localcontext() as decimal_context:
            decimal_context.prec = 2
            budget = self.calculate((request("a", area, 0.5),), area=area, fraction=0.5)
        self.assertEqual(budget.target_fine2, (area + 1) // 2)
        self.assertEqual(budget.allocations[0].allocated_fine2, budget.target_fine2)

    def test_strategy_and_admission_flags_do_not_change_budget_arithmetic(self):
        for strategy in Strategy:
            self.assertEqual(self.calculate((request("a"),), strategy=strategy), self.calculate((request("a"),)))

    def test_inputs_are_preserved_and_output_is_immutable_roundtrippable(self):
        extent = TerrainRegionExtent(region_uid="world-region", generation_area_fine2=100)
        resolved = context()
        requests = (request("b"), request("a"))
        before = (extent.model_dump_json(), resolved.model_dump_json(), tuple(r.model_dump_json() for r in requests))
        budget = WaterCoverageBudgetPolicy().calculate(extent, resolved, requests,
            authored_union_fine2=10, available_auto_area_fine2=20)
        self.assertEqual(before, (extent.model_dump_json(), resolved.model_dump_json(), tuple(r.model_dump_json() for r in requests)))
        validate_immutable(budget)
        self.assertEqual(WaterCoverageBudget.model_validate_json(budget.model_dump_json()), budget)

    def test_raw_inputs_and_runtime_context_cannot_enter_typed_boundary(self):
        policy = WaterCoverageBudgetPolicy()
        extent = TerrainRegionExtent(region_uid="world-region", generation_area_fine2=100)
        for bad_extent, bad_context, bad_requests in (
                (extent.model_dump(), context(), ()), (extent, context().model_dump(), ()),
                (extent, WaterGenerationContext.root(object()), ()),
                (extent, context(), [request("a")]), (extent, context(), (request("a").model_dump(),))):
            with self.subTest(extent=bad_extent, context=bad_context, requests=bad_requests), self.assertRaises(TypeError):
                policy.calculate(bad_extent, bad_context, bad_requests, authored_union_fine2=0, available_auto_area_fine2=100)

    def test_invalid_areas_fractions_and_duplicate_identities_fail(self):
        for kwargs in ({"authored": -1}, {"authored": True}, {"available": 1.5}, {"available": -1},
                       {"available": "10"}, {"authored": 101}, {"authored": 10, "available": 91}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.calculate(**kwargs)
        for requests in ((request("a"), request("a")), (request("a", 101),),
                         (request("a", 10), request("b", 11)), (request("a", 10, region="world-region"),),
                         (request("a").model_copy(update={"target_fraction": float("nan")}),),
                         (request("a").model_copy(update={"generation_area_fine2": True}),)):
            with self.subTest(requests=requests), self.assertRaises(ValueError):
                self.calculate(requests)
        with self.assertRaises(ValueError):
            WaterCoverageBudgetPolicy().calculate(
                TerrainRegionExtent(region_uid="world-region", generation_area_fine2=100),
                context().model_copy(update={"level": Scope.WATER_BODY}), (),
                authored_union_fine2=0, available_auto_area_fine2=100)
