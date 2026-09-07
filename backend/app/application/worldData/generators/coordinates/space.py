from enum import StrEnum


class CoordinateSpace(StrEnum):
    WORLD_SURFACE_GRID = "world_surface_grid"
    WORLD_FINE_GRID = "world_fine_grid"
    LOCATION_FINE_GRID = "location_fine_grid"
