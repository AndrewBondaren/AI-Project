"""Application refs owned by one surface materialization request; never cached."""

from dataclasses import dataclass

from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields


@dataclass(frozen=True, slots=True)
class SurfaceWorkingMaps:
    climate: ClimateWorkingFields
    terrain: TerrainWorkingFields
    hydrology: HydrologyWorkingFields
