"""Explicit observation scope in macro coordinates, independent of bake scope."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.materialize.climateWorkingFields import (
    ClimateWorkingFields,
)
from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import (
    HydrologyWorkingFields,
)
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import (
    TerrainWorkingFields,
)
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology

if TYPE_CHECKING:
    from app.application.worldData.planning.legacy.surfaceTerrainContext import SurfaceTerrainContext


@dataclass(frozen=True)
class FactConsumerContext:
    surface: SurfaceTerrainContext | None
    cells: tuple[tuple[int, int], ...]
    # Profiles already resolved by the caller from world data; no domain/world reads here.
    climate_profiles: Mapping[str, ClimateZoneProfile] | None = None

    # Request-local typed observations projected from the captured plan.
    local_field: ClimateAnchorField | None = None
    relief_z: Mapping[tuple[int, int], int] | None = None
    hydro: Mapping[tuple[int, int], MapCellHydrology] | None = None
    surface_z: Mapping[tuple[int, int], int] | None = None

    # Domain-owned request views (PC-11.5). Migration-only dual channel: an
    # instance carries either these refs or the legacy fields above, never a mix;
    # the legacy fields are removed in PC-11.7 with their remaining callers.
    climate: ClimateWorkingFields | None = None
    terrain: TerrainWorkingFields | None = None
    hydrology: HydrologyWorkingFields | None = None
