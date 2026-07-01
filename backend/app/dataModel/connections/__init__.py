"""
SCH-WORLD-CONN — `worlds.connection_type_registry` (N1-W-06).

Эталон: fixtures/world_template.json, docs/tz_structure_connections.md §2.
"""

from app.dataModel.connections.connectionType import ConnectionTypeEntry, WorldConnectionTypeRegistry

__all__ = [
    "ConnectionTypeEntry",
    "WorldConnectionTypeRegistry",
]
