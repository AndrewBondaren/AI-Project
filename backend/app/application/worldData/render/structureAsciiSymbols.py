"""Debug ASCII glyphs for ``system_building_element`` — indoor grid + L2 city overlay.

Not player UX. One table for pack city dump and structure ``gridRenderer``.
"""

from __future__ import annotations

from app.application.worldData.facingArrows import FACING_ARROW
from app.dataModel.spatial.facing import Facing, coerce_facing_wire
from app.dataModel.structure.enums.buildingElement import (
    STAIR_DIRECTIONAL_ELEMENTS,
    StructureElement,
)

STRUCTURE_ELEMENT_SYMBOLS: dict[StructureElement, str] = {
    StructureElement.WALL: "#",
    StructureElement.FLOOR: ".",
    StructureElement.DOOR: "D",
    StructureElement.STAIR_FLOOR: "_",
    StructureElement.VOID: " ",
    StructureElement.WINDOW: "O",
    StructureElement.ARROW_SLIT: "|",
    StructureElement.PORTHOLE: "o",
    StructureElement.VENT: "v",
    StructureElement.COLUMN: "C",
    StructureElement.RAILING: "r",
    StructureElement.TRAPDOOR: "T",
    StructureElement.LADDER: "H",
    StructureElement.ARCHWAY: "'",
    StructureElement.ROOF: "^",
    StructureElement.GATE: "G",
}

STRUCTURE_ASCII_LEGEND = (
    "structure: #=wall .=floor D=door O=window _=stair_floor ^=roof G=gate "
    "C=column '=archway ↑↓→←=stairs T=trapdoor H=ladder"
)


def _as_element(element: object) -> StructureElement | None:
    if element is None or element == "":
        return None
    if isinstance(element, StructureElement):
        return element
    try:
        return StructureElement(str(element))
    except ValueError:
        return None


def symbol_for_building_element(
    element: object,
    *,
    facing: object | None = None,
) -> str:
    """Glyph for a building element. Unknown element → ``?``. No element → ``?``."""
    parsed = _as_element(element)
    if parsed is None:
        return "?"
    if parsed in STAIR_DIRECTIONAL_ELEMENTS:
        facing_parsed = coerce_facing_wire(facing)
        if facing_parsed is None:
            return "?"
        return FACING_ARROW[Facing(facing_parsed)]
    return STRUCTURE_ELEMENT_SYMBOLS.get(parsed, "?")


def render_structure_legend() -> str:
    return STRUCTURE_ASCII_LEGEND
