"""Recipe construction belongs to field strategy preparation, not orchestration."""

from typing import assert_never

from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.identity.uid import EntityUid
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, PlateNoiseRecipe, WaterFieldRecipe
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def _invalid_strategy() -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("water_design", "strategy"),
        "native procedural source requires a field strategy", code=WaterDesignIssueCode.INVALID_STRATEGY.value),))


class WaterFieldRecipeFactory:
    def build(self, strategy: Strategy, inputs: GeoWaterPlacementInput, seed_root: EntityUid) -> WaterFieldRecipe:
        if not isinstance(strategy, Strategy):
            raise _invalid_strategy()
        topology = fine_topology(inputs.topology, inputs.grid.fine_span)
        match strategy:
            case Strategy.CONTINENTAL_NOISE:
                return NoiseRecipe(seed_root=seed_root, topology=topology, noise_policy=inputs.noise_policy)
            case Strategy.PLATE:
                return PlateRecipe(seed_root=seed_root, topology=topology, plate_policy=inputs.plate_policy)
            case Strategy.PLATE_NOISE:
                return PlateNoiseRecipe(seed_root=seed_root, topology=topology, noise_policy=inputs.noise_policy,
                    plate_policy=inputs.plate_policy, composition_policy=inputs.composition_policy)
            case Strategy.AUTHORED_REGION:
                raise _invalid_strategy()
            case _:
                assert_never(strategy)
