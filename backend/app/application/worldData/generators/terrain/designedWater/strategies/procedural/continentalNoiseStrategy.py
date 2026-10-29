"""Bind the continental-noise field and absolute floor recipe, without placement."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.designedWater.draft import ProceduralWaterDesignDraft
from app.dataModel.terrain.designedWater.input import NoiseWaterDesignInput, WaterStrategyInput
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class ContinentalNoiseStrategy:
    """Metadata/depth/z_min come from ready inputs; the strategy owns no defaults."""

    def design(self, input: WaterStrategyInput) -> ProceduralWaterDesignDraft:
        if not isinstance(input, NoiseWaterDesignInput):
            raise PlanBuildFailure((FieldPathError(("strategy",), "continental noise requires noise input",
                code=WaterDesignIssueCode.INVALID_STRATEGY.value),))
        try:
            input = NoiseWaterDesignInput.model_validate(input, strict=True)
            field = NoiseFieldGenerator().build(input)
            profile = FieldFloorProfile(recipe=input.field_policy, level=input.metadata.level,
                depth=input.metadata.default_depth, z_min=input.z_min)
            draft = ProceduralWaterDesignDraft(metadata=input.metadata, field=field, floor_profile=profile,
                floor_z=FineZ(max(input.z_min, input.metadata.level - input.metadata.default_depth)))
            input.validate_draft(draft)
            return draft
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("continental_noise",), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error
