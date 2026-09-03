"""Builtin building layouts when world.building_template_registry is empty."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation import building_layout_templates
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate


def merge_building_registry(world: Any) -> list[BuildingLayoutTemplate]:
    """World layout-shaped rows + engine builtins (world wins on name collision)."""
    return building_layout_templates(world)


def lookup_building_template(world: Any, system_name: str) -> BuildingLayoutTemplate | None:
    for template in merge_building_registry(world):
        if template.system_name == system_name:
            return template
    return None
