"""Unicode facing arrows — shared by structure stairs + world grade ASCII.

Kept outside ``render/`` so ``generators/structure/gridRenderer`` can import
without triggering ``render.__init__`` (circular import).
"""

from __future__ import annotations

from app.dataModel.spatial.facing import Facing

FACING_ARROW: dict[Facing, str] = {
    Facing.NORTH: "↑",
    Facing.NORTHEAST: "↗",
    Facing.EAST: "→",
    Facing.SOUTHEAST: "↘",
    Facing.SOUTH: "↓",
    Facing.SOUTHWEST: "↙",
    Facing.WEST: "←",
    Facing.NORTHWEST: "↖",
}
