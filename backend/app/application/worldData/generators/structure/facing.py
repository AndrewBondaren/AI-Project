from enum import Enum


class Facing(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST  = "east"
    WEST  = "west"

    def __str__(self) -> str:
        return self.value
