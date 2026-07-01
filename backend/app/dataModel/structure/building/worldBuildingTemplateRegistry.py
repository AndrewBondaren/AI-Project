"""Root POJO for `worlds.building_template_registry`."""

from __future__ import annotations

from pydantic import RootModel

from app.dataModel.structure.building.buildingTemplateRegistryEntry import BuildingTemplateRegistryEntry


class WorldBuildingTemplateRegistry(RootModel[list[BuildingTemplateRegistryEntry]]):
    root: list[BuildingTemplateRegistryEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldBuildingTemplateRegistry:
        return cls([])
