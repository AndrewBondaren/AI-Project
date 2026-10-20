"""Lift world topology from macro tiles to fine cells."""

from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


def fine_topology(topology: WorldTopology, tile_macro: int) -> WorldTopology:
    """Macro-tile topology lifted to fine cells; the same seam rules apply."""
    bounds = topology.bounds
    return WorldTopology(mode=topology.mode, bounds=WorldBounds(
        x_min=bounds.x_min * tile_macro, x_max=(bounds.x_max + 1) * tile_macro - 1,
        y_min=bounds.y_min * tile_macro, y_max=(bounds.y_max + 1) * tile_macro - 1,
    ))


