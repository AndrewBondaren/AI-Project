"""Surface dependency vocabulary; generic planning accepts independent PlanSlot values."""

from enum import StrEnum


class SurfacePlanSlot(StrEnum):
    CLIMATE_BASE = "climate_base"
    TERRAIN_BASE = "terrain_base"
    WATER_PLACEMENT = "water_placement"
    RELIEF = "relief"
    HYDROLOGY_ROUTES = "hydrology_routes"
    RIVER_RELIEF = "river_relief"
    HYDROLOGY = "hydrology"
    CLIMATE_LOCAL = "climate_local"
