"""The adapter validates joins and delegates geometry; policy and field generation stay outside."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from pydantic import TypeAdapter

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.policy.policyResolver import PolicyResolver
from app.application.worldData.generators.terrain.designedWater.preparation.coastlineConstraintPreparer import CoastlineConstraintPreparer
from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource
from app.dataModel.placement.intent import PlacementDependency
from app.dataModel.placement.common import DependencyRelation, PlacementMode
from app.dataModel.terrain.designedWater.input import CoastlineWaterDesignInput, AuthoredWaterDesignInput, NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.coastline_source.fixtures import capture, prepare

TARGET = "app.application.worldData.generators.terrain.designedWater.preparation.coastlineWaterSourceAdapter"


class CoastlineSourceAdapterTests(TestCase):
    def test_each_strategy_keeps_exact_source_metadata_context_and_budget(self):
        for strategy,model in ((Strategy.AUTHORED_REGION,AuthoredWaterDesignInput),
                               (Strategy.CONTINENTAL_NOISE,NoiseWaterDesignInput),
                               (Strategy.PLATE,PlateWaterDesignInput),(Strategy.PLATE_NOISE,PlateNoiseWaterDesignInput)):
            value = capture(strategy=strategy,closed=strategy is Strategy.AUTHORED_REGION)
            before = value.geometry_request.model_dump_json()
            result = prepare(value)
            self.assertIsInstance(result,model)
            self.assertIsInstance(result.source,CoastlineWaterSource)
            self.assertEqual(result.source.value,value.source)
            self.assertEqual(result.metadata,value.metadata)
            self.assertEqual(result.context,value.context)
            self.assertEqual(result.budget,value.budget)
            self.assertEqual(value.geometry_request.model_dump_json(),before)
            adapter = TypeAdapter(CoastlineWaterDesignInput)
            self.assertEqual(adapter.validate_json(adapter.dump_json(result)),result)

    def test_declared_only_closed_ring_preserves_authored_geometry(self):
        result = prepare(capture(strategy=Strategy.AUTHORED_REGION,closed=True,auto=False))
        self.assertFalse(result.context.autoresolve)
        self.assertTrue(result.geometry.footprints)
        self.assertIsNone(result.constraints)

    def test_incomplete_open_line_cannot_bypass_declared_only_or_authored_contract(self):
        for value in (capture(auto=False),capture(strategy=Strategy.AUTHORED_REGION,closed=False,auto=False),
                      capture(strategy=Strategy.AUTHORED_REGION,closed=False,auto=True)):
            with patch(TARGET+".prepare_authored_water_geometry",side_effect=AssertionError("geometry")),                  patch.object(CoastlineConstraintPreparer,"prepare",side_effect=AssertionError("geometry")),                  self.assertRaises(PlanBuildFailure):
                prepare(value)

    def test_no_private_policy_budget_or_strategy_execution(self):
        value = capture()
        with patch.object(PolicyResolver,"resolve",side_effect=AssertionError("policy")),              patch.object(WaterCoverageBudgetPolicy,"calculate",side_effect=AssertionError("budget")):
            result = prepare(value)
        self.assertEqual(result.source.value,value.source)

    def test_nonready_admission_rejected_before_geometry(self):
        value = capture(priority=0)
        with patch.object(CoastlineConstraintPreparer,"prepare",side_effect=AssertionError("geometry")),              self.assertRaises(PlanBuildFailure):
            prepare(value)

    def test_nonready_generation_rejected_before_geometry(self):
        from app.dataModel.hydrology.generation.waterGenerationSettings import WorldHydrologyGenerationFields
        from tests.geo1.contracts.test_hydrology_generation import context_for, resolve
        root = WorldHydrologyGenerationFields(enabled=False)
        value = capture()
        disabled = resolve(root,context_for(root))
        with patch.object(CoastlineConstraintPreparer,"prepare",side_effect=AssertionError("geometry")),              self.assertRaises(PlanBuildFailure):
            prepare(replace(value,generation=disabled))
        with self.assertRaises(TypeError):
            prepare(replace(value,generation=value.admission.decision))

    def test_ready_join_rejects_identity_source_and_strategy_mismatches(self):
        value = capture()
        header = value.admission.header
        source_changed = value.source.model_copy(update={"path":tuple(reversed(value.source.path))})
        changes = (replace(value,source=source_changed),
                   replace(value,context=value.context.model_copy(update={"strategy":Strategy.PLATE})),
                   replace(value,metadata=value.metadata.model_copy(update={"source_uid":"another"})),
                   replace(value,budget=value.budget.model_copy(update={"generation_region_uid":"another"})),
                   replace(value,admission=value.admission.model_copy(update={"header":header.model_copy(update={
                       "identity":header.identity.model_copy(update={"world_uid":"another"})})})),
                   replace(value,admission=value.admission.model_copy(update={"header":header.model_copy(update={"mode":PlacementMode.SEMANTIC})})))
        for changed in changes:
            with patch.object(CoastlineConstraintPreparer,"prepare",side_effect=AssertionError("geometry")),                  self.assertRaises(PlanBuildFailure):
                prepare(changed)

    def test_recipe_is_explicit_and_matches_strategy_seed_and_scale(self):
        value = capture()
        for recipe in (None,capture(strategy=Strategy.PLATE).field_policy,
                       value.field_policy.model_copy(update={"seed_root":"another"}),
                       value.field_policy.model_copy(update={"topology":value.geometry_request.topology})):
            with patch.object(CoastlineConstraintPreparer,"prepare",side_effect=AssertionError("geometry")),                  self.assertRaises(PlanBuildFailure):
                prepare(replace(value,field_policy=recipe))
        authored = capture(strategy=Strategy.AUTHORED_REGION,closed=True)
        with self.assertRaises(PlanBuildFailure):
            prepare(replace(authored,field_policy=value.field_policy))

    def test_boundary_and_self_dependency_are_not_water_sources(self):
        value = capture()
        boundary = value.source.model_copy(update={"purpose":CoastlinePurpose.BODY_BOUNDARY,"target_source_uid":"target"})
        with self.assertRaises(PlanBuildFailure):
            prepare(replace(value,source=boundary))
        dependency = PlacementDependency(target_uid="source",relation=DependencyRelation.SUPPORTED_BY)
        header = value.admission.header.model_copy(update={"dependencies":(dependency,)})
        with self.assertRaises(PlanBuildFailure):
            prepare(replace(value,admission=value.admission.model_copy(update={"header":header})))

    def test_preview_runtime_and_requested_output_scope_do_not_change_input(self):
        self.assertEqual(prepare(capture()),prepare(capture(resolution=ResolutionMode.RUNTIME)))
        self.assertNotIn("requested_tiles",capture().__dataclass_fields__)

    def test_topology_modes_preserve_absolute_source_path(self):
        for mode in WorldTopologyMode:
            value = capture(mode=mode)
            result = prepare(value)
            self.assertEqual(result.source.value.path,value.source.path)
            self.assertEqual(result.pre_hydrology_ref,value.geometry_request.pre_hydrology.ref)

    def test_inconsistent_generation_context_does_not_trigger_geometry(self):
        value = capture()
        for changed in (replace(value,generation=capture(auto=False).generation),
                        replace(value,context=value.context.model_copy(update={"autoresolve":False}))):
            with patch.object(CoastlineConstraintPreparer,"prepare",side_effect=AssertionError("geometry")),                  self.assertRaises(PlanBuildFailure):
                prepare(changed)

    def test_raw_join_inputs_are_rejected(self):
        value = capture()
        for changed in (replace(value,source={}),replace(value,geometry_request={}),replace(value,metadata={}),
                        replace(value,context={}),replace(value,budget={}),replace(value,field_policy={})):
            with self.assertRaises(TypeError):
                prepare(changed)
