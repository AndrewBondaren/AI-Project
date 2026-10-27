"""Water runtime specialization; G2 declares its settings and VALUE channels."""

from typing import Self

from pydantic import BaseModel

from app.dataModel.cascade.runtimeContext import CascadeRuntimeContext
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope


class WaterGenerationContext(CascadeRuntimeContext[WaterGenerationScope]):
    @classmethod
    def root(cls, world: object, *, default_sources: tuple[BaseModel, ...] = ()) -> Self:
        return cls.at_root(WaterGenerationScope.ROOT, world, default_sources=default_sources)
