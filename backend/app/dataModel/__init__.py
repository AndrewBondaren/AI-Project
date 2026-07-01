"""Master-data POJOs (SCH-*) — structure, defaults, field policy."""

from app.dataModel.hydrology import WorldHydrology
from app.dataModel.materials import MaterialRegistryEntry, WorldMaterialRegistry
from app.dataModel.policy import FieldPolicy, OptionalOnWire, StrictOnWire, field_policy
from app.dataModel.roads import RoadSettingsEntry, WorldRoadSettings
from app.dataModel.settlement import (
    CitySizeEntry,
    DistrictTemplateEntry,
    SettlementSkeleton,
    WorldCitySizeRegistry,
    WorldDistrictTemplateRegistry,
    WorldLocationMoodRegistry,
)
from app.dataModel.structure import (
    BarrierTemplateEntry,
    BuildingTemplateOutline,
    BuildingTemplateRegistryEntry,
    WorldBarrierTemplateRegistry,
    WorldBuildingTemplateRegistry,
    WorldRoomTypeRegistry,
)
from app.dataModel.terrain import (
    TerrainCategoryEntry,
    TerrainRegistryEntry,
    WorldTerrainCategoryRegistry,
    WorldTerrainRegistry,
    WorldTerrainScalars,
)

__all__ = [
    "BarrierTemplateEntry",
    "BuildingTemplateOutline",
    "BuildingTemplateRegistryEntry",
    "CitySizeEntry",
    "DistrictTemplateEntry",
    "FieldPolicy",
    "MaterialRegistryEntry",
    "OptionalOnWire",
    "RoadSettingsEntry",
    "SettlementSkeleton",
    "StrictOnWire",
    "TerrainCategoryEntry",
    "TerrainRegistryEntry",
    "WorldBarrierTemplateRegistry",
    "WorldBuildingTemplateRegistry",
    "WorldCitySizeRegistry",
    "WorldDistrictTemplateRegistry",
    "WorldHydrology",
    "WorldLocationMoodRegistry",
    "WorldMaterialRegistry",
    "WorldRoadSettings",
    "WorldRoomTypeRegistry",
    "WorldTerrainCategoryRegistry",
    "WorldTerrainRegistry",
    "WorldTerrainScalars",
    "field_policy",
]
