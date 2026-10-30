"""Bind ready procedural source evidence; policy and geometry stay with their owners."""

from pydantic import TypeAdapter

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
