"""Plate base plus bounded noise detail through the single field/draft contract."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.fields.continentalFieldComposer import ContinentalFieldComposer
from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.designedWater.draft import ProceduralWaterDesignDraft
from app.dataModel.terrain.designedWater.input import PlateNoiseWaterDesignInput, WaterStrategyInput
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PlateNoiseStrategy:
    """Bind actual component settings and one floor profile; do not invoke other strategies."""

    def design(self, input: WaterStrategyInput) -> ProceduralWaterDesignDraft:
        if not isinstance(input, PlateNoiseWaterDesignInput):
            raise PlanBuildFailure((FieldPathError(("strategy",), "plate-noise strategy requires plate-noise input",
                code=WaterDesignIssueCode.INVALID_STRATEGY.value),))
        try:
            input = PlateNoiseWaterDesignInput.model_validate(input, strict=True)
            recipe = input.field_policy
            plate = PlateFieldGenerator().build(input)
            noise = NoiseFieldGenerator().build(input) if recipe.composition_policy.detail_weight != 0.0 else None
            field = ContinentalFieldComposer().combine(plate, noise, recipe)
            profile = FieldFloorProfile(recipe=recipe, level=input.metadata.level,
                depth=input.metadata.default_depth, z_min=input.z_min)
            draft = ProceduralWaterDesignDraft(metadata=input.metadata, field=field, floor_profile=profile,
                floor_z=FineZ(max(input.z_min, input.metadata.level - input.metadata.default_depth)))
            input.validate_draft(draft)
            return draft
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("plate_noise_design",), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error
