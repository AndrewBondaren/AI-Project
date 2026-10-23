"""Legacy request-local working view; removed after consumer cutover."""

from dataclasses import dataclass

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


@dataclass(frozen=True)
class SurfaceTerrainContext:
    """Legacy eight-field working copy; no mutable map belongs to the plan cache."""

    pole_field: ClimatePoleField
    local_field: ClimateAnchorField
    coarse_hm: SurfaceHeightmap
    coarse_hydro: dict[tuple[int, int], MapCellHydrology]
    sparse_fine_hydro: dict[tuple[int, int], MapCellHydrology]
    fine_z_overrides: dict[tuple[int, int], int]
    # Before relief objects/basins, as required by the existing light consumer.
    coarse_relief_z: dict[tuple[int, int], int]
    # Final post-river coarse heights. Fine overrides stay in their own map.
    coarse_surface_z: dict[tuple[int, int], int]
