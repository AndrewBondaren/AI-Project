"""Complete constructor-injected dispatch, without defaults or production bindings."""

from types import MappingProxyType
from typing import Self

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.strategies.strategy import DesignedWaterStrategy
from app.application.worldData.generators.terrain.designedWater.strategies.authoredRegionStrategy import AuthoredRegionStrategy
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.continentalNoiseStrategy import ContinentalNoiseStrategy
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateStrategy import PlateStrategy
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateNoiseStrategy import PlateNoiseStrategy
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

    @classmethod
    def builtins(cls) -> Self:
        """Compose stateless implementations; all generation settings stay in inputs."""
        return cls(authored_region=AuthoredRegionStrategy(), continental_noise=ContinentalNoiseStrategy(),
                   plate=PlateStrategy(), plate_noise=PlateNoiseStrategy())

    def get(self, kind: Strategy) -> DesignedWaterStrategy:
        if not isinstance(kind, Strategy):
            raise PlanBuildFailure((FieldPathError(("strategy",), "expected effective water strategy enum",
                code=WaterDesignIssueCode.INVALID_STRATEGY.value),))
        return self._strategies[kind]
