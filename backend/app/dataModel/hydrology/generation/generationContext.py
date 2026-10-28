"""Resolved water fields and provenance; the common cascade executes inheritance."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StrictBool

from app.dataModel.cascade.runtimeContext import CascadeRuntimeContext
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterFraction, WaterGenerationDefaults
from app.dataModel.hydrology.generation.waterGenerationSettings import WATER_AUTORESOLVE, WATER_FRACTION, WATER_STRATEGY
from app.dataModel.hydrology.policy.hydrologyPolicyDefinition import HYDROLOGY_AUTORESOLVE
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind


class WaterGenerationContext(CascadeRuntimeContext[WaterGenerationScope]):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")

    water_fraction: Annotated[WaterFraction | None, WATER_FRACTION] = None
    autoresolve: Annotated[StrictBool | None, WATER_AUTORESOLVE, HYDROLOGY_AUTORESOLVE] = None
    strategy: Annotated[DesignedWaterStrategyKind | None, WATER_STRATEGY] = None

    @classmethod
    def root(cls, world: object, *, default_sources: tuple[BaseModel, ...] | None = None) -> Self:
        if default_sources is None:
            default_sources = (WaterGenerationDefaults.canonical_defaults(),)
        return cls.at_root(WaterGenerationScope.ROOT, world, default_sources=default_sources)
