"""Bind the plate field and captured absolute floor profile; no mountain generation."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.designedWater.draft import ProceduralWaterDesignDraft
from app.dataModel.terrain.designedWater.input import PlateWaterDesignInput, WaterStrategyInput
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PlateStrategy:
    """Ready inputs own settings, depth and z_min; this strategy returns only a draft."""

    def design(self, input: WaterStrategyInput) -> ProceduralWaterDesignDraft:
        if not isinstance(input, PlateWaterDesignInput):
            raise PlanBuildFailure((FieldPathError(("strategy",), "plate strategy requires plate input",
                code=WaterDesignIssueCode.INVALID_STRATEGY.value),))
        try:
            input = PlateWaterDesignInput.model_validate(input, strict=True)
            field = PlateFieldGenerator().build(input)
            profile = FieldFloorProfile(recipe=input.field_policy, level=input.metadata.level,
                depth=input.metadata.default_depth, z_min=input.z_min)
            draft = ProceduralWaterDesignDraft(metadata=input.metadata, field=field, floor_profile=profile,
                floor_z=FineZ(max(input.z_min, input.metadata.level - input.metadata.default_depth)))
            input.validate_draft(draft)
            return draft
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("plate_design",), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error
