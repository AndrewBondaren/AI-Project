"""Builtin fallback `system_material` keys when registry resolve finds no match — tz_city_generation.md §3.1, material resolver."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConstructionMaterialDefaults:
    """Engine defaults per construction use_type / role."""

    wall: str = "stone"
    floor: str = "wood"
    road: str = "dirt_road"
    dominant: str = "stone"

    def for_use_type(self, use_type: str) -> str:
        key = (use_type or "").strip().lower()
        if key == "wall":
            return self.wall
        if key == "floor":
            return self.floor
        if key == "road":
            return self.road
        return self.wall


CONSTRUCTION_MATERIAL_DEFAULTS = ConstructionMaterialDefaults()

DEFAULT_WALL_MATERIAL = CONSTRUCTION_MATERIAL_DEFAULTS.wall
DEFAULT_FLOOR_MATERIAL = CONSTRUCTION_MATERIAL_DEFAULTS.floor
DEFAULT_ROAD_MATERIAL = CONSTRUCTION_MATERIAL_DEFAULTS.road
DEFAULT_DOMINANT_MATERIAL = CONSTRUCTION_MATERIAL_DEFAULTS.dominant
