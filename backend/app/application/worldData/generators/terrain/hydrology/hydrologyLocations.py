"""Geographic NamedLocation filters — D HY-1d. See tz_terrain_hydrology.md § Loader."""

from app.application.worldData.generators.terrain.hydrology.types import (
    GEOGRAPHIC_LOCATION_TYPE,
    GeographicSubtype,
)
from app.db.models.namedLocation import NamedLocation


def is_geographic_location(loc: NamedLocation) -> bool:
    return loc.system_location_type == GEOGRAPHIC_LOCATION_TYPE


def geographic_locations(locations: list[NamedLocation]) -> list[NamedLocation]:
    return [loc for loc in locations if is_geographic_location(loc)]


def geographic_subtype(loc: NamedLocation) -> GeographicSubtype | None:
    """Parse subtype; None if missing or unknown (forward-compat for new subtypes in bundle)."""
    raw = loc.system_location_subtype
    if not raw:
        return None
    try:
        return GeographicSubtype(raw)
    except ValueError:
        return None
