"""Application refs owned by one surface materialization request; never cached."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields

if TYPE_CHECKING:
    from app.application.worldData.regions.inputs.landcoverInputs import LandcoverObservations


@dataclass(frozen=True, slots=True)
class SurfaceWorkingMaps:
    climate: ClimateWorkingFields
    terrain: TerrainWorkingFields
    hydrology: HydrologyWorkingFields
    landcover: LandcoverObservations
