from enum import Enum


class StructureElement(str, Enum):
    WALL        = "wall"
    FLOOR       = "floor"
    DOOR        = "door"
    STAIRCASE   = "staircase"
    COLUMN      = "column"
    RAILING     = "railing"
    GATE        = "gate"
    ROOF        = "roof"
    # Wall openings
    WINDOW      = "window"
    ARROW_SLIT  = "arrow_slit"
    PORTHOLE    = "porthole"
    VENT        = "vent"
    HATCH       = "hatch"


_WALL_OPENING_TYPES: frozenset[StructureElement] = frozenset({
    StructureElement.WINDOW,
    StructureElement.ARROW_SLIT,
    StructureElement.PORTHOLE,
    StructureElement.VENT,
})
