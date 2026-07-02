"""Wire ``system_building_element`` — ENUM-E (tz_locations.md § Building elements).

Engine-closed vocabulary; not N+1 master data. Generators compare via this enum,
not string literals (HY-5).
"""

from __future__ import annotations

from enum import StrEnum


class StructureElement(StrEnum):
    WALL = "wall"
    FLOOR = "floor"
    DOOR = "door"
    STAIRCASE = "staircase"
    COLUMN = "column"
    RAILING = "railing"
    GATE = "gate"
    ROOF = "roof"
    WINDOW = "window"
    ARROW_SLIT = "arrow_slit"
    PORTHOLE = "porthole"
    VENT = "vent"
    HATCH = "hatch"
    STAIR_ANCHOR = "stair_anchor"
    STAIR_FLOOR = "stair_floor"
    TRAPDOOR = "trapdoor"
    LADDER = "ladder"
    ARCHWAY = "archway"
    VOID = "void"

    def is_stair(self) -> bool:
        return self in STAIR_BUILDING_ELEMENTS

    def is_directional_stair(self) -> bool:
        return self in STAIR_DIRECTIONAL_ELEMENTS


WALL_OPENING_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.WINDOW,
    StructureElement.ARROW_SLIT,
    StructureElement.PORTHOLE,
    StructureElement.VENT,
})

STAIR_BUILDING_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.STAIRCASE,
    StructureElement.STAIR_ANCHOR,
    StructureElement.STAIR_FLOOR,
})

PASSABLE_BUILDING_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.VOID,
    StructureElement.ARCHWAY,
})

WALKABLE_BUILDING_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.FLOOR,
    StructureElement.DOOR,
    StructureElement.STAIRCASE,
    StructureElement.STAIR_FLOOR,
    StructureElement.STAIR_ANCHOR,
    StructureElement.LADDER,
    StructureElement.TRAPDOOR,
})

WALL_BUILDING_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.WALL,
    StructureElement.COLUMN,
})

DOOR_BUILDING_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.DOOR,
    StructureElement.ARCHWAY,
})

STAIR_DIRECTIONAL_ELEMENTS: frozenset[StructureElement] = frozenset({
    StructureElement.STAIRCASE,
    StructureElement.STAIR_ANCHOR,
})

# Transitional aliases — prefer public names above.
_WALL_OPENING_TYPES = WALL_OPENING_ELEMENTS
_STAIR_ELEMENTS = STAIR_BUILDING_ELEMENTS
_PASSABLE_ELEMENTS = PASSABLE_BUILDING_ELEMENTS
_WALKABLE_ELEMENTS = WALKABLE_BUILDING_ELEMENTS
_WALL_ELEMENTS = WALL_BUILDING_ELEMENTS
_DOOR_ELEMENTS = DOOR_BUILDING_ELEMENTS
_STAIR_DIRECTIONAL = STAIR_DIRECTIONAL_ELEMENTS
