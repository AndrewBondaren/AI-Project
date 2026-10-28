"""Dispatch uses supplied implementations and propagates explicit domain failures."""

from unittest import TestCase

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest, WaterCoverageBudget
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.contracts.strategies.fixtures import inputs, draft_for


class SuppliedStrategy:
    def __init__(self):
        self.calls = []

    def design(self, input):
        self.calls.append(input)
        return input.validate_draft(draft_for(input))


class FailingStrategy:
    def design(self, input):
        raise PlanBuildFailure((FieldPathError(input.metadata.source_path, "failure",
            code=WaterDesignIssueCode.INVALID_STRATEGY.value),))


class StrategyDispatchTests(TestCase):
    def test_complete_dispatch_returns_exact_injected_implementations(self):
        implementations = [SuppliedStrategy() for _ in Strategy]
        factory = DesignedWaterStrategyFactory(authored_region=implementations[0],
            continental_noise=implementations[1], plate=implementations[2], plate_noise=implementations[3])
        for strategy, implementation in zip(Strategy, implementations):
            self.assertIs(factory.get(strategy), implementation)
            value = inputs(strategy)
            self.assertEqual(factory.get(strategy).design(value), draft_for(value))
            self.assertEqual(implementation.calls, [value])

    def test_missing_bindings_and_invalid_kinds_are_explicit_failures(self):
        strategy = SuppliedStrategy()
        for missing in ("authored_region", "continental_noise", "plate", "plate_noise"):
            kwargs = dict(authored_region=strategy, continental_noise=strategy, plate=strategy, plate_noise=strategy)
            del kwargs[missing]
            with self.assertRaises(TypeError):
                DesignedWaterStrategyFactory(**kwargs)
        factory = DesignedWaterStrategyFactory(authored_region=strategy, continental_noise=strategy, plate=strategy, plate_noise=strategy)
        for invalid in ("plate", "unknown", None, 0, []):
            with self.assertRaises(PlanBuildFailure) as raised:
                factory.get(invalid)
            self.assertEqual(raised.exception.issues[0].code, WaterDesignIssueCode.INVALID_STRATEGY.value)
        self.assertEqual(strategy.calls, [])

    def test_existing_failure_is_not_replaced_by_success(self):
        strategy = FailingStrategy()
        factory = DesignedWaterStrategyFactory(authored_region=strategy, continental_noise=strategy, plate=strategy, plate_noise=strategy)
        with self.assertRaises(PlanBuildFailure):
            factory.get(Strategy.PLATE).design(inputs(Strategy.PLATE))


class BudgetRecordTests(TestCase):
    def budget(self, **updates):
        return WaterCoverageBudget.model_validate(dict(region_uid="world-region", area_fine2=100,
            target_fraction=0.6, target_fine2=60, authored_union_fine2=40, residual_fine2=20,
            allocations=(inputs().budget,)) | updates)

    def test_records_roundtrip_without_computing_or_resolving_a_budget(self):
        request = BodyCoverageRequest(source_uid="source", generation_region_uid="region",
            generation_area_fine2=16, target_fraction=0.5)
        for value in (request, inputs().budget, self.budget()):
            validate_immutable(value)
            self.assertEqual(type(value).model_validate_json(value.model_dump_json()), value)
        self.assertEqual(self.budget(authored_union_fine2=80, residual_fine2=0, allocations=()).residual_fine2, 0)

    def test_invalid_numeric_identity_and_cap_records_rejected(self):
        for update in ({"area_fine2": True}, {"area_fine2": -1}, {"target_fraction": float("nan")},
                       {"target_fraction": 1.1}, {"target_fine2": 101}, {"authored_union_fine2": 101},
                       {"residual_fine2": 21}, {"allocations": (inputs().budget,) * 2},
                       {"residual_fine2": 0, "authored_union_fine2": 60}, {"region_uid": ""}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                self.budget(**update)
        allocation = inputs().budget
        for update in ({"allocated_fine2": 9}, {"requested_fine2": -1}, {"allocated_fine2": False}):
            with self.assertRaises(ValidationError):
                type(allocation).model_validate(allocation.model_copy(update=update))
