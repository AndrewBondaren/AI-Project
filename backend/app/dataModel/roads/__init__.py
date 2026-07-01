"""
SCH-WORLD-ROAD-SETTINGS — `worlds.road_settings` JSON array.

Эталон: docs/tz_structure_connections.md §3.6, fixtures/world_template.json (future).
"""

from app.dataModel.roads.roadSettingsEntry import RoadSettingsEntry
from app.dataModel.roads.worldRoadSettings import WorldRoadSettings

__all__ = [
    "RoadSettingsEntry",
    "WorldRoadSettings",
]
