"""Static map anchor locations (CL-12)."""

from app.db.models.namedLocation import NamedLocation


def static_map_anchors(locations: list[NamedLocation]) -> list[NamedLocation]:
    return [
        loc for loc in locations
        if loc.map_x is not None and loc.map_y is not None
        and loc.map_z is not None and not loc.is_mobile
    ]


def static_climate_poles(locations: list[NamedLocation]) -> list[NamedLocation]:
    from app.application.worldData.generators.climate.climatePole import CLIMATE_POLE_TYPE

    return [
        loc for loc in static_map_anchors(locations)
        if loc.system_location_type == CLIMATE_POLE_TYPE
    ]
