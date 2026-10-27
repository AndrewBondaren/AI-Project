"""Terminal domain values; source settings keep nullable inheritance."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat

from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind

type WaterFraction = Annotated[StrictFloat, Field(ge=0, le=1, allow_inf_nan=False)]


class WaterGenerationDefaults(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always", validate_default=True)

    water_fraction: WaterFraction = 0.60
    autoresolve: StrictBool = False
    strategy: DesignedWaterStrategyKind = DesignedWaterStrategyKind.CONTINENTAL_NOISE

    @classmethod
    def canonical_defaults(cls) -> Self:
        return cls()
