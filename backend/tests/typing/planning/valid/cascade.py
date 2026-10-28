"""Immutable cascade results preserve domain subtype and scope axis."""

from typing import assert_type

from app.dataModel.cascade.runtimeContext import freeze_resolved_context
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope
from app.dataModel.hydrology.generation.generationContext import (
    ResolvedWaterGenerationContext, WaterGenerationContext,
)
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind


def valid_resolved_cascade(runtime: WaterGenerationContext) -> ResolvedWaterGenerationContext:
    result = freeze_resolved_context(runtime, ResolvedWaterGenerationContext)
    assert_type(result, ResolvedWaterGenerationContext)
    assert_type(result.level, WaterGenerationScope)
    assert_type(result.provenance, tuple[tuple[str, tuple[WaterGenerationScope, str]], ...])
    assert_type(result.water_fraction, float)
    assert_type(result.autoresolve, bool)
    assert_type(result.strategy, DesignedWaterStrategyKind)
    return result
