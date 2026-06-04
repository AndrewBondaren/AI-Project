from enum import Enum


class StructureElement(str, Enum):
    WALL      = "wall"
    FLOOR     = "floor"
    DOOR      = "door"
    WINDOW    = "window"
    STAIRCASE = "staircase"
    COLUMN    = "column"
    RAILING   = "railing"
    GATE      = "gate"
    ROOF      = "roof"
