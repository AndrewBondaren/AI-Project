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


class BuiltinStrategyCompositionTests(TestCase):
    def cases(self):
        from tests.geo1.preparation.fixtures import procedural_case
        from app.dataModel.topology.worldBounds import WorldBounds
        return tuple(inputs(kind) if kind is Strategy.AUTHORED_REGION else procedural_case(strategy=kind,
            allocated=8, bounds=WorldBounds(x_min=-2, x_max=3, y_min=-1, y_max=2))[0] for kind in Strategy)

    def prepare(self, factory, value):
        from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
        from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
        draft = factory.get(value.strategy).design(value)
        value.validate_draft(draft)
        return draft, DesignedWaterPlacementPreparer().prepare(value, draft, selection_policy=WaterFieldSelectionPolicy())

    def test_all_builtins_feed_the_same_preparer_and_preserve_ready_evidence(self):
        from unittest.mock import patch
        from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
        factory = DesignedWaterStrategyFactory.builtins()
        for value in self.cases():
            before = value.model_dump()
            with self.subTest(strategy=value.strategy), patch(
                    "app.application.worldData.placement.adapters.water.shape_cells", side_effect=AssertionError("geometry repeated")):
                draft, prepared = self.prepare(factory, value)
                self.assertEqual(prepared.metadata, value.metadata)
                self.assertEqual(prepared.pre_hydrology_ref, value.pre_hydrology_ref)
                self.assertEqual(prepared.floor_z, draft.floor_z)
                self.assertEqual(prepared.floor_profile, draft.floor_profile)
                self.assertEqual(WaterDesignPreparation.model_validate_json(prepared.model_dump_json()), prepared)
                self.assertEqual(value.model_dump(), before)

    def test_fresh_factories_replay_the_same_drafts_and_geometry(self):
        first, other = DesignedWaterStrategyFactory.builtins(), DesignedWaterStrategyFactory.builtins()
        for value in self.cases():
            with self.subTest(strategy=value.strategy):
                expected = self.prepare(first, value)
                self.assertEqual(self.prepare(first, value), expected)
                self.assertEqual(self.prepare(other, value), expected)

    def test_one_factory_uses_each_requests_captured_recipe_without_retaining_settings(self):
        factory = DesignedWaterStrategyFactory.builtins()
        for value in self.cases():
            if value.strategy is Strategy.AUTHORED_REGION:
                continue
            changed = type(value).model_validate(value.model_copy(update={"seed_root": "other-seed",
                "field_policy": value.field_policy.model_copy(update={"seed_root": "other-seed"})}))
            with self.subTest(strategy=value.strategy):
                before = factory.get(value.strategy).design(value)
                after = factory.get(changed.strategy).design(changed)
                self.assertEqual(after.field.recipe, changed.field_policy)
                self.assertEqual(after.floor_profile.recipe, changed.field_policy)
                self.assertNotEqual(after.field.samples, before.field.samples)
                self.assertEqual(factory.get(value.strategy).design(value), before)

    def test_wrong_input_retains_the_selected_strategys_domain_failure(self):
        from tests.geo1.preparation.fixtures import procedural_case
        factory = DesignedWaterStrategyFactory.builtins()
        value, _ = procedural_case(strategy=Strategy.PLATE)
        with self.assertRaises(PlanBuildFailure) as failure:
            factory.get(Strategy.CONTINENTAL_NOISE).design(value)
        self.assertEqual(failure.exception.issues[0].code, WaterDesignIssueCode.INVALID_STRATEGY.value)


class ProceduralSourceJoinTests(TestCase):
    def case(self, kind=Strategy.CONTINENTAL_NOISE, *, enabled=True, admitted=True):
        from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy
        from app.application.policy.policyResolver import PolicyResolver
        from app.dataModel.cascade.runtimeContext import freeze_resolved_context
        from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
        from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings, CategoryWaterGenerationSettings, BodyWaterGenerationSettings
        from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
        from app.dataModel.hydrology.sources.waterDesignSource import ProceduralSource
        from app.dataModel.terrain.designedWater.input import WaterDesignInput
        from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
        from app.dataModel.placement.lifecycle.header import PlacementHeader
        from app.dataModel.placement.intent import PlacementIdentity
        from app.dataModel.placement.common import PlacementMode
        from app.dataModel.validation.enums.resolutionMode import ResolutionMode
        from tests.geo1.placement_policy.fixtures import bind, execute
        from tests.geo1.preparation.fixtures import procedural_case
        ready, _ = procedural_case(strategy=kind)
        binding = bind_hydrology_generation_policy(enabled=enabled,
            generation=WorldWaterGenerationSettings(autoresolve=True, strategy=kind, water_fraction=0.5),
            defaults=WaterGenerationDefaults(), category=CategoryWaterGenerationSettings(),
            body=BodyWaterGenerationSettings(), root_path=("hydrology",), context_path=("resolved",))
        generation = PolicyResolver().resolve(binding.spec, binding.inputs, binding.facts, mode=ResolutionMode.RUNTIME)
        values = {name: getattr(ready, name) for name in WaterDesignInput.model_fields}
        values["context"] = freeze_resolved_context(binding.context, ResolvedWaterGenerationContext)
        shared = WaterDesignInput[ProceduralSource](**values)
        admission = PlacementAdmissionInput(header=PlacementHeader(identity=PlacementIdentity(world_uid="world",
            source_uid="source", region_uid="placement-region"), mode=PlacementMode.ABSOLUTE,
            dependencies=(), permitted_overlaps=(), separations=()),
            decision=execute(bind(source=shared.source, enabled=admitted, strategy=kind)))
        return shared, dict(generation=generation, admission=admission, field_policy=ready.field_policy, z_min=ready.z_min)

    def join(self, value, **kwargs):
        from app.application.worldData.generators.terrain.designedWater.preparation.proceduralWaterSourceAdapter import ProceduralWaterSourceAdapter
        return ProceduralWaterSourceAdapter().prepare_source(value, **kwargs)

    def test_three_ready_sources_feed_builtin_strategies_and_shared_preparer(self):
        from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
        from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
        for kind in (Strategy.CONTINENTAL_NOISE, Strategy.PLATE, Strategy.PLATE_NOISE):
            shared, kwargs = self.case(kind)
            before = shared.model_dump()
            with self.subTest(kind=kind):
                result = self.join(shared, **kwargs)
                draft = DesignedWaterStrategyFactory.builtins().get(result.strategy).design(result)
                prepared = DesignedWaterPlacementPreparer().prepare(result, draft, selection_policy=WaterFieldSelectionPolicy())
                self.assertEqual(result.strategy, kind)
                self.assertEqual(result.source, shared.source)
                self.assertEqual(result.context, shared.context)
                self.assertEqual(prepared.pre_hydrology_ref, shared.pre_hydrology_ref)
                self.assertEqual(prepared.floor_profile.recipe, kwargs["field_policy"])
                self.assertEqual(result.z_min, kwargs["z_min"])
                self.assertEqual(shared.model_dump(), before)

    def test_non_ready_generation_or_admission_is_not_prepared(self):
        for kwargs in ({"enabled": False}, {"admitted": False}):
            shared, values = self.case(**kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(PlanBuildFailure):
                self.join(shared, **values)

    def test_foreign_admission_source_and_world_are_rejected(self):
        shared, values = self.case()
        for update in ({"world_uid": "other"}, {"source_uid": "other"}):
            admission = values["admission"]
            header = admission.header.model_copy(update={"identity": admission.header.identity.model_copy(update=update)})
            with self.subTest(update=update), self.assertRaises(PlanBuildFailure):
                self.join(shared, **(values | {"admission": admission.model_copy(update={"header": header})}))

    def test_strategy_recipe_seed_and_world_floor_must_match_ready_evidence(self):
        shared, values = self.case()
        _, other = self.case(Strategy.PLATE)
        variants = ({"field_policy": other["field_policy"]},
            {"field_policy": values["field_policy"].model_copy(update={"seed_root": "other"})},
            {"z_min": shared.metadata.level}, {"z_min": True})
        for update in variants:
            with self.subTest(update=update), self.assertRaises(PlanBuildFailure):
                self.join(shared, **(values | update))
        context = shared.context.model_copy(update={"autoresolve": False})
        with self.assertRaises(PlanBuildFailure):
            self.join(shared.model_copy(update={"context": context}), **values)

    def test_self_support_is_not_sent_to_strategy_preparation(self):
        from app.dataModel.placement.intent import PlacementDependency
        from app.dataModel.placement.common import DependencyRelation
        shared, values = self.case()
        admission = values["admission"]
        header = admission.header.model_copy(update={"dependencies": (PlacementDependency(
            target_uid=admission.header.identity.region_uid, relation=DependencyRelation.RESOLVED),)})
        with self.assertRaises(PlanBuildFailure):
            self.join(shared, **(values | {"admission": admission.model_copy(update={"header": header})}))

    def test_authored_source_and_forged_metadata_cannot_enter_procedural_join(self):
        shared, values = self.case()
        with self.assertRaises(PlanBuildFailure):
            self.join(inputs(Strategy.AUTHORED_REGION), **values)
        with self.assertRaises(PlanBuildFailure):
            self.join(shared.model_copy(update={"metadata": shared.metadata.model_copy(update={"source_uid": "other"})}), **values)
