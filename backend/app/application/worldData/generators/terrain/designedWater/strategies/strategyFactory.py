"""Complete constructor-injected dispatch, without defaults or production bindings."""

from types import MappingProxyType

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.strategies.strategy import DesignedWaterStrategy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class DesignedWaterStrategyFactory:
    def __init__(self, *, authored_region: DesignedWaterStrategy,
                 continental_noise: DesignedWaterStrategy, plate: DesignedWaterStrategy,
                 plate_noise: DesignedWaterStrategy) -> None:
        self._strategies = MappingProxyType({
            Strategy.AUTHORED_REGION: authored_region,
            Strategy.CONTINENTAL_NOISE: continental_noise,
            Strategy.PLATE: plate,
            Strategy.PLATE_NOISE: plate_noise,
        })

    def get(self, kind: Strategy) -> DesignedWaterStrategy:
        if not isinstance(kind, Strategy):
            raise PlanBuildFailure((FieldPathError(("strategy",), "expected effective water strategy enum",
                code=WaterDesignIssueCode.INVALID_STRATEGY.value),))
        return self._strategies[kind]
