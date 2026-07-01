"""Connection edge width builtins — tz_structure_connections.md §3.4."""

from __future__ import annotations

# Fixed width per connection_type; None = no physical cells.
FIXED_WIDTH_CELLS: dict[str, int | None] = {
    "trail": 1,
    "dirt_road": 2,
    "alley": 2,
    "yard_path": 1,
    "portal": None,
    "air_route": None,
    "sea_route": None,
}

LANE_WIDTH_CELLS = 2
LANE_BASED_CONNECTION_TYPES = frozenset({"road", "highway", "bridge"})
UNKNOWN_CONNECTION_WIDTH_FALLBACK = 2


def _lane_based_width(lanes_per_side: int, bidirectional: bool) -> int:
    one_side = lanes_per_side * LANE_WIDTH_CELLS
    return one_side * 2 if bidirectional else one_side


def width_cells_for_connection(
    connection_type: str,
    lanes_per_side: int = 1,
    bidirectional: bool = True,
) -> int | None:
    """
    Edge width in map cells.
    None — types without physical cells (portal, air_route, sea_route).
    settlement_gate inherits upstream width — resolved in SettlementAssembler, not here.
    """
    ct = (connection_type or "").strip().lower()
    if ct in FIXED_WIDTH_CELLS:
        return FIXED_WIDTH_CELLS[ct]
    if ct in LANE_BASED_CONNECTION_TYPES:
        return _lane_based_width(lanes_per_side, bidirectional)
    return UNKNOWN_CONNECTION_WIDTH_FALLBACK
