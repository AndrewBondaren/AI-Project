"""Domain adapters prepare inputs; spatial competition belongs to the common pass."""

from .water import prepare_water_placements, resolved_water_placements
from .waterTypes import WaterPlacementContext, WaterPlacementPreparation

__all__ = ["prepare_water_placements", "resolved_water_placements",
           "WaterPlacementContext", "WaterPlacementPreparation"]
