"""
Вычисляет width_cells для ConnectionEdge по типу дороги и количеству полос.
Правила — см. tz_structure_connections.md §3.4.
"""

from app.dataModel.roads.connectionWidthDefaults import width_cells_for_connection

resolve_width = width_cells_for_connection

__all__ = ["resolve_width"]
