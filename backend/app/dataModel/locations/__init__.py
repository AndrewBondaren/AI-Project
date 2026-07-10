"""
SCH-WORLD-LOC-TYPE — `worlds.location_type_registry` (N1-W-07).

Эталон: fixtures/world_template.json (legacy map), docs/tz_locations.md (target array).
"""

from app.dataModel.locations.locationFootprintPolicy import (
    named_location_uses_settlement_meter_footprint,
    uses_settlement_meter_footprint,
)
from app.dataModel.locations.locationType import (
    LocationTypeEntry,
    LocationTypeSubtypeEntry,
    WorldLocationTypeRegistry,
)
from app.dataModel.locations.enums import GeographicSubtype, GEOGRAPHIC_LOCATION_TYPE
from app.dataModel.locations.namedLocation import BundleNamedLocation

__all__ = [
    "BundleNamedLocation",
    "GEOGRAPHIC_LOCATION_TYPE",
    "GeographicSubtype",
    "LocationTypeEntry",
    "LocationTypeSubtypeEntry",
    "WorldLocationTypeRegistry",
    "uses_settlement_meter_footprint",
    "named_location_uses_settlement_meter_footprint",
]
