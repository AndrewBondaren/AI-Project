"""Closed surface coordinate maps — tz_terrain_generation § Форма мира."""

from enum import StrEnum


class WorldTopologyMode(StrEnum):
    PLANAR = "planar"
    WRAPPED = "wrapped"
    SPHERE = "sphere"
