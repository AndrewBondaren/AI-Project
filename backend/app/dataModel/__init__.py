"""Master-data POJOs (SCH-*) — structure, defaults, field policy."""

from app.dataModel.climate import (
    ClimateZoneEntry,
    SeasonTempOffsets,
    WeatherTypeEntry,
    WorldClimateScalars,
    WorldClimateZoneRegistry,
    WorldWeatherTypeRegistry,
)
from app.dataModel.connections import ConnectionTypeEntry, WorldConnectionTypeRegistry
from app.dataModel.economy import EconomyTierEntry, WorldEconomyTierRegistry
from app.dataModel.hydrology import WorldHydrology
from app.dataModel.materials import MaterialRegistryEntry, WorldMaterialRegistry
from app.dataModel.annotationPolicy import AnnotationPolicy, OptionalOnWire, StrictOnWire, field_policy
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
    "ClimateZoneEntry",
    "ConnectionTypeEntry",
    "DistrictTemplateEntry",
    "EconomyTierEntry",
    "AnnotationPolicy",
    "MaterialRegistryEntry",
    "OptionalOnWire",
    "RoadSettingsEntry",
    "SeasonTempOffsets",
    "SettlementSkeleton",
    "StrictOnWire",
    "TerrainCategoryEntry",
    "TerrainRegistryEntry",
    "WeatherTypeEntry",
    "WorldBarrierTemplateRegistry",
    "WorldBuildingTemplateRegistry",
    "WorldCitySizeRegistry",
    "WorldClimateScalars",
    "WorldClimateZoneRegistry",
    "WorldConnectionTypeRegistry",
    "WorldDistrictTemplateRegistry",
    "WorldEconomyTierRegistry",
    "WorldHydrology",
    "WorldLocationMoodRegistry",
    "WorldMaterialRegistry",
    "WorldRoadSettings",
    "WorldRoomTypeRegistry",
    "WorldTerrainCategoryRegistry",
    "WorldTerrainRegistry",
    "WorldTerrainScalars",
    "WorldWeatherTypeRegistry",
    "field_policy",
]
