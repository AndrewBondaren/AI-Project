"""Authored water side of a closed coastline."""

from enum import StrEnum


class WaterSide(StrEnum):
    INTERIOR = "interior"
    EXTERIOR = "exterior"
