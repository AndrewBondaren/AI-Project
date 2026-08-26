"""3×3 ERROR diagram for an unclosed cell — consume ASCII, not dump glyphs."""

from __future__ import annotations

from app.dataModel.spatial.facing import COMPACT_LETTER, Facing

# Same 3×3 as tz_terrain_relief_consume ASCII (center is the terrain cell).
_CELL_SLOTS: tuple[tuple[Facing | None, ...], ...] = (
    (Facing.NORTHWEST, Facing.NORTH, Facing.NORTHEAST),
    (Facing.WEST, None, Facing.EAST),
    (Facing.SOUTHWEST, Facing.SOUTH, Facing.SOUTHEAST),
)


def open_slot_diagram(missing: set[Facing]) -> tuple[str, str]:
    """``.`` = unclosed edge; ``#`` = closed edge or center. ``open`` = compact letters."""

    def glyph(slot: Facing | None) -> str:
        if slot is None:
            return "#"
        return "." if slot in missing else "#"

    diagram = " ".join("".join(glyph(slot) for slot in row) for row in _CELL_SLOTS)
    open_ids = ",".join(
        COMPACT_LETTER[slot]
        for row in _CELL_SLOTS
        for slot in row
        if slot is not None and slot in missing
    )
    return diagram, open_ids
