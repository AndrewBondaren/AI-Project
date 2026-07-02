"""Builtin building layouts when world.building_template_registry is empty."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation import building_layout_templates


def merge_building_registry(world: Any) -> list[dict]:
    """World registry + engine builtins (world wins on name collision)."""
    return building_layout_templates(world)


def lookup_building_template(world: Any, system_name: str) -> dict | None:
    for template in merge_building_registry(world):
        if template.get("system_name") == system_name:
            return template
    return None
