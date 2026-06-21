from enum import Enum


class StructureElement(str, Enum):
    def __str__(self) -> str:
        return self.value

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
    # Staircase elements
    STAIR_ANCHOR = "stair_anchor"
    STAIR_FLOOR  = "stair_floor"
    TRAPDOOR     = "trapdoor"
    LADDER       = "ladder"
    # Spatial / structural
    ARCHWAY      = "archway"
    VOID         = "void"


_WALL_OPENING_TYPES: frozenset[StructureElement] = frozenset({
    StructureElement.WINDOW,
    StructureElement.ARROW_SLIT,
    StructureElement.PORTHOLE,
    StructureElement.VENT,
})

_STAIR_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.STAIRCASE,
    StructureElement.STAIR_ANCHOR,
    StructureElement.STAIR_FLOOR,
})

# Физически открытое пространство — не блокирует объём и headroom
_PASSABLE_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.VOID,
    StructureElement.ARCHWAY,
})

# Можно переместиться через / по (для валидаторов дверей и арок)
_WALKABLE_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.FLOOR,
    StructureElement.DOOR,
    StructureElement.STAIRCASE,
    StructureElement.STAIR_FLOOR,
    StructureElement.STAIR_ANCHOR,
    StructureElement.LADDER,
    StructureElement.TRAPDOOR,
})

_WALL_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.WALL,
    StructureElement.COLUMN,
})

_DOOR_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.DOOR,
    StructureElement.ARCHWAY,
})

_STAIR_DIRECTIONAL: frozenset[StructureElement] = frozenset({
    StructureElement.STAIRCASE,
    StructureElement.STAIR_ANCHOR,
})
