"""Explicit observation scope in macro coordinates, independent of bake scope."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.dataModel.climate.enums.climateZone import ClimateZoneProfile

if TYPE_CHECKING:
    from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import SurfaceTerrainContext


@dataclass(frozen=True)
class FactConsumerContext:
    surface: SurfaceTerrainContext | None
    cells: tuple[tuple[int, int], ...]
    # Profiles already resolved by the caller from world data; no domain/world reads here.
    climate_profiles: Mapping[str, ClimateZoneProfile] | None = None
