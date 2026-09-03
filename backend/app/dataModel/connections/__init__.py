"""
SCH-WORLD-CONN — `worlds.connection_type_registry` (N1-W-06).

Эталон: fixtures/world_template.json, docs/tz_structure_connections.md §2.
"""

from app.dataModel.connections.connectionType import (
    HYDROLOGY_CONNECTION_TYPE_KEYS,
    LANE_BASED_CONNECTION_TYPE_KEYS,
    ROAD_MASK_CONNECTION_TYPE_KEYS,
    ConnectionTypeEntry,
    WorldConnectionTypeRegistry,
)
from app.dataModel.connections.enums import ConnectionNodeType, GraphLevel, PortalType

__all__ = [
    "HYDROLOGY_CONNECTION_TYPE_KEYS",
    "LANE_BASED_CONNECTION_TYPE_KEYS",
    "ROAD_MASK_CONNECTION_TYPE_KEYS",
    "ConnectionNodeType",
    "ConnectionTypeEntry",
    "GraphLevel",
    "PortalType",
    "WorldConnectionTypeRegistry",
]
