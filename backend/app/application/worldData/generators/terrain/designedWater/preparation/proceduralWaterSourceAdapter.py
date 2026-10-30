"""Bind ready procedural source evidence; policy and geometry stay with their owners."""

from pydantic import TypeAdapter
from dataclasses import dataclass
from app.application.worldData.generators.hydrology.sources.waterSourceMetadataFactory import WaterSourceMetadataFactory
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.fieldRecipeFactory import WaterFieldRecipeFactory
from app.dataModel.hydrology.policy.proceduralSourceAdmission import ProceduralSourceAdmissions
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.terrain.designedWater.coverage.budget import WaterCoverageBudget
from app.dataModel.terrain.designedWater.input import WaterStrategyInput

from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision, WaterDesignDecision
from app.dataModel.hydrology.sources.waterDesignSource import ProceduralSource
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, WaterFieldRecipe
from app.dataModel.terrain.designedWater.input import (
    NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput, WaterDesignInput,
)
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

_GENERATION = TypeAdapter(HydrologyGenerationDecision)
_ADMISSION = TypeAdapter(WaterDesignDecision)
_RECIPE = TypeAdapter(WaterFieldRecipe)


class ProceduralWaterSourceAdapter:
    def prepare_source(
        self, input: WaterDesignInput[ProceduralSource], *, generation: HydrologyGenerationDecision,
        admission: PlacementAdmissionInput, field_policy: WaterFieldRecipe, z_min: FineZ,
    ) -> NoiseWaterDesignInput[ProceduralSource] | PlateWaterDesignInput[ProceduralSource] | PlateNoiseWaterDesignInput[ProceduralSource]:
        try:
            shared = WaterDesignInput[ProceduralSource].model_validate(input, strict=True)
            generation = _GENERATION.validate_python(generation, strict=True)
            admission = PlacementAdmissionInput.model_validate(admission, strict=True)
            decision = _ADMISSION.validate_python(admission.decision, strict=True)
            recipe = _RECIPE.validate_python(field_policy, strict=True)
            if generation.state is not PolicyState.READY or decision.state is not PolicyState.READY:
                raise ValueError("procedural input requires ready generation and admission")
            if generation.require_behavior() is not HydrologyExecutionMode.AUTORESOLVE or not shared.context.autoresolve:
                raise ValueError("procedural source requires resolved AUTORESOLVE")
            if decision.require_behavior() is not shared.strategy or recipe.strategy is not shared.strategy:
                raise ValueError("procedural admission and recipe must match the resolved strategy")
            identity = admission.header.identity
            if (identity.source_uid != shared.source.value.source_uid
                    or identity.world_uid != shared.pre_hydrology.ref.key.world_uid):
                raise ValueError("procedural admission must match the captured source and world")
            if any(d.target_uid in (identity.source_uid, identity.region_uid) for d in admission.header.dependencies):
                raise ValueError("procedural source cannot depend on itself or its future water")
            values = {name: getattr(shared, name) for name in WaterDesignInput.model_fields}
            values.update(field_policy=recipe, z_min=z_min)
            if isinstance(recipe, NoiseRecipe):
                return NoiseWaterDesignInput[ProceduralSource].model_validate(values, strict=True)
            if isinstance(recipe, PlateRecipe):
                return PlateWaterDesignInput[ProceduralSource].model_validate(values, strict=True)
            return PlateNoiseWaterDesignInput[ProceduralSource].model_validate(values, strict=True)
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("water_source",), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error


@dataclass(frozen=True)
class CapturedProceduralWaterInputs:
    """Bind captured native source facts to ready strategy inputs; no P2 lifecycle."""
    inputs: GeoWaterPlacementInput
    sources: ProceduralSourceAdmissions
    pre_hydrology: PlanEnvelope[TerrainPlan]
    regions: TerrainRegionPlan
    seed_root: EntityUid

    @classmethod
    def capture(cls, inputs: GeoWaterPlacementInput, sources: ProceduralSourceAdmissions,
                pre_hydrology: PlanEnvelope[TerrainPlan], regions: TerrainRegionPlan,
                seed_root: EntityUid) -> "CapturedProceduralWaterInputs":
        inputs = GeoWaterPlacementInput.model_validate(inputs, strict=True)
        sources = ProceduralSourceAdmissions.model_validate(sources, strict=True)
        pre_hydrology = PlanEnvelope[TerrainPlan].model_validate(pre_hydrology, strict=True)
        regions = TerrainRegionPlan.model_validate(regions, strict=True)
        if (inputs.declared_world_bounds is None) != (regions.snapshot.world_region is None):
            raise PlanBuildFailure((FieldPathError(("water_source", "world_bounds"),
                "captured bounds presence must match the terrain world region",
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))
        for binding in sources.sources:
            if binding.admission.decision.state in (PolicyState.READY, PolicyState.WAITING_SUPPORT):
                WaterFieldRecipeFactory.require_strategy(binding.context.strategy)
        return cls(inputs, sources, pre_hydrology, regions, seed_root)

    def prepare(self, admission: PlacementAdmissionInput, budget: WaterCoverageBudget | None) -> WaterStrategyInput:
        uid = admission.header.identity.source_uid
        binding = next((binding for binding in self.sources.sources if binding.source.value.source_uid == uid), None)
        if budget is None or binding is None:
            raise PlanBuildFailure((FieldPathError(("water_source",), "ready source requires captured binding and shared world budget",
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))
        source, context = binding.source, binding.context
        allocation = next((item for item in budget.allocations if item.source_uid == uid), None)
        region = self.regions.snapshot.region_for(source.value.generation_region_uid)
        coverage = next((item for item in self.regions.coverages if item.region_uid == source.value.generation_region_uid), None)
        if allocation is None or region is None or coverage is None:
            raise PlanBuildFailure((FieldPathError(binding.source_path, "ready source requires exact allocation/region/coverage",
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))
        metadata = WaterSourceMetadataFactory().build(source, default_water_level=self.inputs.default_water_level,
            seas=self.inputs.seas, lakes=self.inputs.lakes, rim_level=None, source_path=binding.source_path)
        shared = WaterDesignInput[ProceduralSource](strategy=context.strategy, source=source, metadata=metadata,
            context=context, region=region, budget=allocation, seed_root=self.seed_root, topology=self.inputs.topology,
            grid=self.inputs.grid, pre_hydrology=self.pre_hydrology, region_coverage=coverage)
        recipe = WaterFieldRecipeFactory().build(context.strategy, self.inputs, self.seed_root)
        return ProceduralWaterSourceAdapter().prepare_source(shared, generation=binding.generation,
            admission=admission, field_policy=recipe, z_min=self.inputs.z_min)
