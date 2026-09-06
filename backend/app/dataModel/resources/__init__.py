"""
SCH-WORLD-RESOURCE — `worlds.resource_type_registry` JSON array (N1-W-10).

Extract subjects only. Эталон: docs/tz_locations.md § resources.
"""

from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.resources.resourceTypeEntry import ResourceTypeEntry
from app.dataModel.resources.worldResourceTypeRegistry import WorldResourceTypeRegistry

__all__ = [
    "ResourceKind",
    "ResourceTypeEntry",
    "WorldResourceTypeRegistry",
]
