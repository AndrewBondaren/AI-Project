"""Geographic NamedLocation filters — D HY-1d. See tz_terrain_hydrology.md § Loader."""

from app.dataModel.locations.enums.geographicSubtype import (
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
    return GeographicSubtype.from_wire(loc.system_location_subtype)
