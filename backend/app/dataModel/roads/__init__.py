"""
SCH-WORLD-ROAD-SETTINGS — `worlds.road_settings` JSON array.

Эталон: docs/tz_structure_connections.md §3.6, fixtures/world_template.json (future).
"""

from app.dataModel.roads.connectionWidthDefaults import (
    FIXED_WIDTH_CELLS,
    LANE_BASED_CONNECTION_TYPES,
    LANE_WIDTH_CELLS,
    UNKNOWN_CONNECTION_WIDTH_FALLBACK,
    width_cells_for_connection,
)
from app.dataModel.roads.roadSettingsEntry import RoadSettingsEntry
from app.dataModel.roads.worldRoadSettings import WorldRoadSettings

__all__ = [
    "FIXED_WIDTH_CELLS",
    "LANE_BASED_CONNECTION_TYPES",
    "LANE_WIDTH_CELLS",
    "RoadSettingsEntry",
    "UNKNOWN_CONNECTION_WIDTH_FALLBACK",
    "WorldRoadSettings",
    "width_cells_for_connection",
]
