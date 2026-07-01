"""Master-data POJOs (SCH-*) — structure, defaults, field policy."""

from app.dataModel.climate import (
    ClimateZone,
    ClimateZoneEntry,
    ClimateZoneProfile,
    ClimateZoneProfileData,
    SeasonTempOffsets,
    WeatherTypeEntry,
    WorldClimateScalars,
    WorldClimateZoneRegistry,
    WorldWeatherTypeRegistry,
)
from app.dataModel.connections import ConnectionTypeEntry, WorldConnectionTypeRegistry
from app.dataModel.economy import EconomyTierEntry, WorldEconomyTierRegistry
from app.dataModel.hydrology import WorldHydrology
from app.dataModel.locations import (
    LocationTypeEntry,
    LocationTypeSubtypeEntry,
    WorldLocationTypeRegistry,
)
from app.dataModel.lore import LoreRegistryEntry, WorldLoreRegistry
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
    "ClimateZone",
    "ClimateZoneEntry",
    "ClimateZoneProfile",
    "ClimateZoneProfileData",
    "ConnectionTypeEntry",
    "DistrictTemplateEntry",
    "EconomyTierEntry",
    "LocationTypeEntry",
    "LocationTypeSubtypeEntry",
    "LoreRegistryEntry",
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
    "WorldLocationTypeRegistry",
    "WorldLoreRegistry",
    "WorldMaterialRegistry",
    "WorldRoadSettings",
    "WorldRoomTypeRegistry",
    "WorldTerrainCategoryRegistry",
    "WorldTerrainRegistry",
    "WorldTerrainScalars",
    "WorldWeatherTypeRegistry",
    "field_policy",
]
