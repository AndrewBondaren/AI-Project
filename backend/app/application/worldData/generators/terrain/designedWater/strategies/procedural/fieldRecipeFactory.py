"""Recipe construction belongs to field strategy preparation, not orchestration."""

from pydantic import TypeAdapter, ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.identity.uid import EntityUid
from app.dataModel.terrain.designedWater.fields.field import WaterFieldRecipe, WaterFieldRecipeContext
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


_RECIPE = TypeAdapter(WaterFieldRecipe)


class WaterFieldRecipeFactory:
    def build(self, strategy: Strategy, inputs: GeoWaterPlacementInput, seed_root: EntityUid) -> WaterFieldRecipe:
        try:
            context = WaterFieldRecipeContext(strategy=strategy, seed_root=seed_root,
                topology=fine_topology(inputs.topology, inputs.grid.fine_span), noise_policy=inputs.noise_policy,
                plate_policy=inputs.plate_policy, composition_policy=inputs.composition_policy)
            return _RECIPE.validate_python(context, strict=True, from_attributes=True)
        except ValidationError as error:
            raise PlanBuildFailure((FieldPathError(("water_design", "strategy"),
                "native procedural source requires a field strategy", code=WaterDesignIssueCode.INVALID_STRATEGY.value),)) from error
