"""Room attachment sides (§3.4); BOTH preserves the generator fallback."""
from enum import StrEnum


class AttachWall(StrEnum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    BOTH = "both"
    ANY = "any"
