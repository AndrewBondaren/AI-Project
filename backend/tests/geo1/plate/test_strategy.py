"""Plate draft, shared quota selection and notice/floor propagation."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateStrategy import PlateStrategy
from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest
from app.dataModel.terrain.designedWater.draft import ProceduralWaterDesignDraft
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy,WaterDesignIssueCode as Code
from app.dataModel.topology.worldBounds import WorldBounds
from tests.geo1.plate.fixtures import case
from tests.geo1.contracts.strategies.fixtures import inputs
from tests.geo1.coastline_source.fixtures import capture,prepare


class PlateStrategyTests(TestCase):
    def test_field_metadata_and_actual_world_floor_bound_survive(self):
        input=case();before=input.model_dump_json()
        draft=PlateStrategy().design(input)
        self.assertEqual(draft.field,PlateFieldGenerator().build(input))
        self.assertEqual(draft.metadata,input.metadata)
        self.assertEqual(draft.floor_profile.recipe,input.field_policy)
        self.assertEqual(draft.floor_profile.z_min,input.z_min)
        self.assertEqual(draft.floor_profile.depth,input.metadata.default_depth)
        self.assertEqual(draft.floor_z,max(input.z_min,input.metadata.level-input.metadata.default_depth))
        self.assertNotIn("footprints",type(draft).model_fields)
        self.assertNotIn("candidates",type(draft).model_fields)
        self.assertEqual(input.model_dump_json(),before)
        self.assertEqual(ProceduralWaterDesignDraft.model_validate_json(draft.model_dump_json()),draft)

    def test_floor_uses_captured_z_min_without_terrain_minimum_default(self):
        input=case();input=type(input).model_validate(input.model_copy(update={"z_min":-3}))
        self.assertEqual(PlateStrategy().design(input).floor_z,-3)
        self.assertEqual(PlateStrategy().design(input).floor_profile.z_min,-3)

    def test_tiny_world_notice_reaches_preparation_without_mutating_policy(self):
        input=case(bounds=WorldBounds(x_min=0,x_max=0,y_min=0,y_max=0),span=1)
        input=type(input).model_validate(input.model_copy(update={"budget":input.budget.model_copy(update={"allocated_fine2":1})}))
        draft=PlateStrategy().design(input)
        result=DesignedWaterPlacementPreparer().prepare(input,draft,selection_policy=WaterFieldSelectionPolicy())
        self.assertEqual(result.notices,draft.field.notices)
        self.assertEqual(result.notices[0].code,Code.PLATE_COUNT_ADJUSTED.value)
        self.assertEqual(input.field_policy.plate_policy.plate_count,12)
        self.assertEqual(len(result.candidates[0].footprint.cells),1)

    def test_zero_sixty_and_full_quota_use_common_budget_and_selection(self):
        fields=[]
        for fraction,expected in ((0.0,0),(.6,15),(1.0,25)):
            input=case(bounds=WorldBounds(x_min=0,x_max=4,y_min=0,y_max=4))
            context=input.context.model_copy(update={"level":Scope.WORLD,"water_fraction":fraction})
            budget=WaterCoverageBudgetPolicy().calculate(input.region,context,
                (BodyCoverageRequest(source_uid=input.metadata.source_uid,generation_region_uid=input.region.region_uid,
                    generation_area_fine2=input.region.generation_area_fine2,target_fraction=fraction),),
                authored_union_fine2=0,available_auto_area_fine2=input.region.generation_area_fine2)
            input=type(input).model_validate(input.model_copy(update={"context":input.context.model_copy(update={"water_fraction":fraction}),"budget":budget.allocations[0]}))
            draft=PlateStrategy().design(input);fields.append(draft.field)
            if not expected:
                with self.assertRaises(PlanBuildFailure) as caught:
                    DesignedWaterPlacementPreparer().prepare(input,draft,selection_policy=WaterFieldSelectionPolicy())
                self.assertEqual(caught.exception.issues[0].code,Code.EMPTY_GENERATION_TARGET.value)
            else:
                result=DesignedWaterPlacementPreparer().prepare(input,draft,selection_policy=WaterFieldSelectionPolicy())
                self.assertEqual(len(result.candidates[0].footprint.cells),expected)
        self.assertEqual(fields[0],fields[1]);self.assertEqual(fields[1],fields[2])

    def test_coastline_masks_and_both_normal_notices_are_preserved(self):
        captured=capture(strategy=Strategy.PLATE)
        req=captured.geometry_request
        req=type(req).model_validate(req.model_copy(update={"seas":req.seas.model_copy(update={"max_area_fraction":.15})}))
        captured=replace(captured,geometry_request=req,field_policy=captured.field_policy.model_copy(update={"plate_policy":PlateGenerationPolicy(plate_count=1000)}))
        input=prepare(captured);draft=PlateStrategy().design(input)
        result=DesignedWaterPlacementPreparer().prepare(input,draft,selection_policy=WaterFieldSelectionPolicy())
        self.assertTrue(input.constraints.required_cells <= result.candidates[0].footprint.cells <= input.constraints.allowed_cells)
        self.assertEqual(result.floor_profile,draft.floor_profile)
        self.assertIn(Code.PLATE_COUNT_ADJUSTED.value,{notice.code for notice in result.notices})
        self.assertIn("WATER_PLACEMENT_CAP_REACHED",{notice.code for notice in result.notices})

    def test_strategy_never_uses_noise_policy_budget_or_spatial_selection(self):
        input=case()
        with patch.object(NoiseFieldGenerator,"build",side_effect=AssertionError("noise")),              patch.object(NoiseFieldGenerator,"sample",side_effect=AssertionError("noise")),              patch.object(PolicyResolver,"resolve",side_effect=AssertionError("policy")),              patch.object(WaterCoverageBudgetPolicy,"calculate",side_effect=AssertionError("budget")),              patch.object(DesignedWaterPlacementPreparer,"prepare",side_effect=AssertionError("selection")):
            PlateStrategy().design(input)

    def test_wrong_strategy_and_unrepresentable_input_fail_explicitly(self):
        for input in (inputs(Strategy.AUTHORED_REGION),inputs(Strategy.CONTINENTAL_NOISE),inputs(Strategy.PLATE_NOISE)):
            with self.assertRaises(PlanBuildFailure) as caught:PlateStrategy().design(input)
            self.assertEqual(caught.exception.issues[0].code,Code.INVALID_STRATEGY.value)
        with self.assertRaises(PlanBuildFailure):PlateStrategy().design(case(policy=PlateGenerationPolicy(blend_length_fraction=1e308)))
