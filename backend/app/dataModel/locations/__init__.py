"""
SCH-WORLD-LOC-TYPE — `worlds.location_type_registry` (N1-W-07).

Эталон: fixtures/world_template.json (legacy map), docs/tz_locations.md (target array).
"""

from app.dataModel.locations.locationType import (
    LocationTypeEntry,
    LocationTypeSubtypeEntry,
    WorldLocationTypeRegistry,
)

__all__ = [
    "LocationTypeEntry",
    "LocationTypeSubtypeEntry",
    "WorldLocationTypeRegistry",
]
