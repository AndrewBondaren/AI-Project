"""Relief grade enums — tz_terrain_relief R2/R13/R19/R26."""

from __future__ import annotations

from enum import StrEnum


class ReliefSideKind(StrEnum):
    """Graded face vs vertical face — not landcover / system_terrain."""

    SHEER = "sheer"
    SLOPE = "slope"


class ReliefContext(StrEnum):
    """Pick / template context — exactly one per ReliefTemplate (R17)."""

    MOUNTAIN = "mountain"
    OPEN_LAND = "open_land"
    SHORE = "shore"
    ROAD_SHOULDER = "road_shoulder"


class ReliefConditionTerrain(StrEnum):
    """Closed corridor/patch landcover class for conditions (R26/R34)."""

    MOUNTAIN = "mountain"
    PLAINS = "plains"
    FOREST = "forest"
    RAVINE = "ravine"
    SHORE = "shore"


class ReliefSlopePolicy(StrEnum):
    """Three policies per terrain condition (R26)."""

    SLOPE_DOWN = "slope_down"
    SLOPE_UP = "slope_up"
    SLOPE_NONE = "slope_none"


class ReliefPickMode(StrEnum):
    """Per-context template pick (R19)."""

    FIXED = "fixed"
    RANDOM = "random"
    ROUND_ROBIN = "round_robin"


class MountainSideRecipeMode(StrEnum):
    """Detected side_recipe mode (R33) — runtime label, not wire.

    Wire-letter values A–D are historical; logs use ``log_label()``
    (weights|pattern|fixed|empty) to avoid clash with ribbon Mode A|B.
    """

    WEIGHTS = "A"
    PATTERN = "B"
    FIXED = "C"
    EMPTY = "D"

    def log_label(self) -> str:
        return {
            MountainSideRecipeMode.WEIGHTS: "weights",
            MountainSideRecipeMode.PATTERN: "pattern",
            MountainSideRecipeMode.FIXED: "fixed",
            MountainSideRecipeMode.EMPTY: "empty",
        }[self]
