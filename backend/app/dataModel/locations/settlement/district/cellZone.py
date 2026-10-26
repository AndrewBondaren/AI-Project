"""Footprint-cell zone — CITY-T-4e / tz_city_generation.md §9.6."""

from __future__ import annotations

from enum import StrEnum


class CellZone(StrEnum):
    """Position of a global cell in the settlement footprint grid."""

    CENTER = "center"
    EDGE = "edge"
    INNER = "inner"
