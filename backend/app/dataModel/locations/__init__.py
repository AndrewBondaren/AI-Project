"""
SCH-WORLD-LOC-TYPE — `worlds.location_type_registry` (N1-W-07).

Эталон: fixtures/world_template.json (legacy map), docs/tz_locations.md (target array).
"""

from app.dataModel.locations.locationFootprintPolicy import (
    is_settlement_map_site,
    named_location_is_settlement_map_site,
    named_location_uses_settlement_fine_footprint,
    uses_settlement_fine_footprint,
)
from app.dataModel.locations.locationType import (
    LocationTypeEntry,
    LocationTypeSubtypeEntry,
    WorldLocationTypeRegistry,
)
from app.dataModel.locations.enums import EntryRole, GeographicSubtype, GEOGRAPHIC_LOCATION_TYPE
from app.dataModel.locations.namedLocation import BundleNamedLocation

__all__ = [
    "BundleNamedLocation",
    "EntryRole",
    "GEOGRAPHIC_LOCATION_TYPE",
    "GeographicSubtype",
    "LocationTypeEntry",
    "LocationTypeSubtypeEntry",
    "WorldLocationTypeRegistry",
    "uses_settlement_fine_footprint",
    "named_location_uses_settlement_fine_footprint",
    "is_settlement_map_site",
    "named_location_is_settlement_map_site",
]
