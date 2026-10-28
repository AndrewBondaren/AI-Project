"""Closed strategy identity, shared by water settings and terrain consumers."""

from enum import StrEnum


class DesignedWaterStrategyKind(StrEnum):
    AUTHORED_REGION = "authored_region"
    CONTINENTAL_NOISE = "continental_noise"
    PLATE = "plate"
    PLATE_NOISE = "plate_noise"


class WaterDesignIssueCode(StrEnum):
    INVALID_STRATEGY = "WATER_DESIGN_INVALID_STRATEGY"
