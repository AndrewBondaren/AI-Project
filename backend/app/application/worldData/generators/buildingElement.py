from enum import Enum


class BuildingElement(str, Enum):
    WALL      = "wall"
    FLOOR     = "floor"
    DOOR      = "door"
    WINDOW    = "window"
    STAIRCASE = "staircase"
    COLUMN    = "column"
    RAILING   = "railing"
    GATE      = "gate"
    ROOF      = "roof"
