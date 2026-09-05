"""Builtin building layouts when world.building_template_registry is empty."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.application.jsonValidation.worldRow import world_building_layout_overrides
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.dataModel.structure.building.worldBuildingLayoutDefaults import canonical_defaults


def assemble_building_catalog(
    world: Any,
    library_layouts: Iterable[BuildingLayoutTemplate] = (),
) -> BuildingCatalog:
    """builtins ⊕ SQL library layouts ⊕ world layout-shaped rows (later wins)."""
    ordered: list[BuildingLayoutTemplate] = []
    ordered.extend(canonical_defaults())
    ordered.extend(library_layouts)
    ordered.extend(world_building_layout_overrides(world))
    return BuildingCatalog.from_layouts(ordered)


def merge_building_registry(world: Any) -> list[BuildingLayoutTemplate]:
    """World layout-shaped rows + engine builtins (world wins on name collision)."""
    return list(assemble_building_catalog(world).layouts)


def lookup_building_template(
    world: Any,
    system_name: str,
    catalog: BuildingCatalog | None = None,
) -> BuildingLayoutTemplate | None:
    if catalog is not None:
        return catalog.by_system_name(system_name)
    return assemble_building_catalog(world).by_system_name(system_name)
