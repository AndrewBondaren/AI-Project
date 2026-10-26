"""Explicit observation scope in macro coordinates, independent of bake scope."""

from dataclasses import dataclass

from app.application.worldData.generators.climate.materialize.climateWorkingFields import (
    ClimateWorkingFields,
)
from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import (
    HydrologyWorkingFields,
)
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import (
    TerrainWorkingFields,
)


@dataclass(frozen=True)
class FactConsumerContext:
    cells: tuple[tuple[int, int], ...]
    # None means that this domain was not observed; consumers never fabricate it.
    climate: ClimateWorkingFields | None = None
    terrain: TerrainWorkingFields | None = None
    hydrology: HydrologyWorkingFields | None = None
