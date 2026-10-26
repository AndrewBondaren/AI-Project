"""Wire building context for structure generation."""

from __future__ import annotations

from enum import StrEnum

#This enum is not used in the generator.
class BuildingContext(StrEnum):
    INDOOR = "indoor"
    UNDERGROUND = "underground"
    NAUTICAL = "nautical"
