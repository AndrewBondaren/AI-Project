"""Authored strategy: consume prepared geometry, preserve metadata and floor."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.placement.adapters.waterTypes import WaterPreparationCode
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.designedWater.draft import AuthoredWaterDesignDraft
from app.dataModel.terrain.designedWater.input import AuthoredWaterDesignInput, WaterStrategyInput
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class AuthoredRegionStrategy:
    def design(self, input: WaterStrategyInput) -> AuthoredWaterDesignDraft:
        if not isinstance(input, AuthoredWaterDesignInput):
            raise PlanBuildFailure((FieldPathError(("strategy",), "authored strategy requires authored input",
                code=WaterDesignIssueCode.INVALID_STRATEGY.value),))
        try:
            input = AuthoredWaterDesignInput.model_validate(input, strict=True)
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("authored_design",), str(error),
                code=WaterPreparationCode.SNAPSHOT.value),)) from error
        # Geometry was calculated before metadata. In particular, lake level
        # already came from geometry.rim_level: do not rasterize or resolve again.
        geometry = input.geometry
        floor = (FineZ(input.source.value.floor_z) if isinstance(input.source, AuthoredBasinSource)
                 else FineZ(input.metadata.level - input.metadata.default_depth))
        if not geometry.z_min <= floor < input.metadata.level:
            raise PlanBuildFailure((FieldPathError(input.metadata.source_path,
                "authored floor must satisfy world z_min <= floor < water level; authored floor is never clamped",
                code=WaterPreparationCode.FLOOR.value),))
        draft = AuthoredWaterDesignDraft(metadata=input.metadata, footprints=geometry.footprints,
            coordinate_space=geometry.coordinate_space, floor_z=floor, floor_profile=None)
        input.validate_draft(draft)
        return draft
