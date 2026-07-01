"""
SCH-WORLD-CLIMATE — climate master data on `worlds`.

Эталон: fixtures/world_template.json, docs/tz_climate.md.
"""

from app.dataModel.climate.climateZone import ClimateZoneEntry, WorldClimateZoneRegistry
from app.dataModel.climate.enums import ClimateZone, ClimateZoneProfile, ClimateZoneProfileData
from app.dataModel.climate.weatherType import WeatherTypeEntry, WorldWeatherTypeRegistry
from app.dataModel.climate.worldClimateScalars import SeasonTempOffsets, WorldClimateScalars

__all__ = [
    "ClimateZone",
    "ClimateZoneEntry",
    "ClimateZoneProfile",
    "ClimateZoneProfileData",
    "SeasonTempOffsets",
    "WeatherTypeEntry",
    "WorldClimateScalars",
    "WorldClimateZoneRegistry",
    "WorldWeatherTypeRegistry",
]
