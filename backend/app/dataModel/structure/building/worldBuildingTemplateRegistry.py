"""Root POJO for `worlds.building_template_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.structure.building.buildingTemplateRegistryEntry import BuildingTemplateRegistryEntry


class WorldBuildingTemplateRegistry(RootModel[list[BuildingTemplateRegistryEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-BUILDING-TEMPLATE"

    root: list[BuildingTemplateRegistryEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldBuildingTemplateRegistry:
        return cls([])
