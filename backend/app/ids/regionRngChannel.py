"""Region RNG channels — wilderness-regions-mechanic §5 #4, DET-1."""

from enum import StrEnum


class RegionRngChannel(StrEnum):
    """Named streams for future UidKind.REGION consumers."""

    SEED = "seed"
    CLAIM = "claim"
    EDGE = "edge"
    DENSITY = "density"
