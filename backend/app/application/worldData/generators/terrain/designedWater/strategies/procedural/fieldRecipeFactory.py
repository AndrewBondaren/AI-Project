"""Recipe construction belongs to field strategy preparation, not orchestration."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.identity.uid import EntityUid
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, PlateNoiseRecipe, WaterFieldRecipe
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class WaterFieldRecipeFactory:
    @staticmethod
    def require_strategy(strategy: Strategy) -> None:
        if not isinstance(strategy, Strategy) or strategy not in (
                Strategy.CONTINENTAL_NOISE, Strategy.PLATE, Strategy.PLATE_NOISE):
            raise PlanBuildFailure((FieldPathError(("water_design", "strategy"),
                "native procedural source requires a field strategy", code=WaterDesignIssueCode.INVALID_STRATEGY.value),))

    def build(self, strategy: Strategy, inputs: GeoWaterPlacementInput, seed_root: EntityUid) -> WaterFieldRecipe:
        self.require_strategy(strategy)
        topology = fine_topology(inputs.topology, inputs.grid.fine_span)
        if strategy is Strategy.CONTINENTAL_NOISE:
            return NoiseRecipe(seed_root=seed_root, topology=topology, noise_policy=inputs.noise_policy)
        if strategy is Strategy.PLATE:
            return PlateRecipe(seed_root=seed_root, topology=topology, plate_policy=inputs.plate_policy)
        return PlateNoiseRecipe(seed_root=seed_root, topology=topology, noise_policy=inputs.noise_policy,
            plate_policy=inputs.plate_policy, composition_policy=inputs.composition_policy)
