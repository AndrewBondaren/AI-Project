from enum import StrEnum


class CoordinateSpace(StrEnum):
    WORLD_SURFACE_GRID = "world_surface_grid"
    WORLD_LOCAL_METERS = "world_local_meters"
    LOCATION_LOCAL_METERS = "location_local_meters"
