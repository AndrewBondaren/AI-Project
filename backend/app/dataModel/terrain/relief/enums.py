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
    RAVINE = "ravine"


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


class ReliefGradeObstaclePolicy(StrEnum):
    """World ``relief_grade_obstacle_policy`` — tz_terrain_relief R36n.

    ``free_gap`` = free cells outward until obstacle footprint (0 if next is obstacle).
    """

    TRUNCATE_SKIP = "truncate_skip"
    ALLOW_FLUSH = "allow_flush"

    def effective_outward_length(self, requested_length: int, free_gap: int) -> int:
        """``L_eff``; ``< 1`` → caller skips grade (R36m)."""
        requested = max(0, int(requested_length))
        gap = max(0, int(free_gap))
        if self is ReliefGradeObstaclePolicy.TRUNCATE_SKIP:
            return max(0, min(requested, gap - 1))
        return max(0, min(requested, gap))


class CanalObstacleEntity(StrEnum):
    """``canal_obstacle_policy.entities`` — tz_terrain_relief R36p.

    ``road`` ≠ ReliefContext ``road_shoulder``; ``plains`` ≠ ``open_land``.
    """

    ROAD = "road"
    MOUNTAIN = "mountain"
    FOREST = "forest"
    PLAINS = "plains"
    SHORE = "shore"
    ALL = "all"


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
