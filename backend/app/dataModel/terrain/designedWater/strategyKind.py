"""Closed strategy identity, shared by water settings and terrain consumers."""

from enum import StrEnum


class DesignedWaterStrategyKind(StrEnum):
    AUTHORED_REGION = "authored_region"
    CONTINENTAL_NOISE = "continental_noise"
    PLATE = "plate"
    PLATE_NOISE = "plate_noise"


class WaterDesignIssueCode(StrEnum):
    INVALID_STRATEGY = "WATER_DESIGN_INVALID_STRATEGY"
    INVALID_PREPARATION_INPUT = "WATER_DESIGN_INVALID_PREPARATION_INPUT"
    EMPTY_GENERATION_TARGET = "WATER_DESIGN_EMPTY_GENERATION_TARGET"
    CONSTRAINT_CONFLICT = "WATER_DESIGN_CONSTRAINT_CONFLICT"
    PLATE_COUNT_ADJUSTED = "WATER_DESIGN_PLATE_COUNT_ADJUSTED"
    COVERAGE_SHORTFALL = "WATER_DESIGN_COVERAGE_SHORTFALL"
