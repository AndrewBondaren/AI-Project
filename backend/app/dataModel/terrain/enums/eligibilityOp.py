"""Closed operations for terrain coverage eligibility rules."""

from enum import StrEnum


class EligibilityOp(StrEnum):
    GTE = "gte"
    LTE = "lte"
    IN_RANGE = "in_range"
    FLAG = "flag"
