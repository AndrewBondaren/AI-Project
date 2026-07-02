"""
SCH-WORLD-CLIMATE — climate master data on `worlds`.

Эталон: fixtures/world_template.json, docs/tz_climate.md.
"""

from app.dataModel.climate.climateAnchorInfluenceDefaults import (
    LOCAL_INFLUENCE_BLEND_OUTER,
    local_influence_fraction,
)
from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND, ClimatePoleBlendDefaults
from app.dataModel.climate.climatePoleTemperature import (
    POLE_TEMPERATURE_INSET_FRACTION,
    derived_pole_temperature,
)
from app.dataModel.climate.climateZone import ClimateZoneEntry, WorldClimateZoneRegistry
from app.dataModel.climate.enums import (
    CLIMATE_POLE_LOCATION_TYPE,
    ClimatePoleMode,
    ClimatePolePreset,
    ClimatePoleSpec,
    ClimateZone,
    ClimateZoneProfile,
    ClimateZoneProfileData,
    DEFAULT_CLIMATE_POLE_MODE,
    DEFAULT_CLIMATE_POLE_PRESET,
    PoleKind,
    PoleSource,
    pole_specs_for_preset,
)
from app.dataModel.climate.weatherType import WeatherTypeEntry, WorldWeatherTypeRegistry
from app.dataModel.climate.worldClimateScalars import SeasonTempOffsets, WorldClimateScalars

__all__ = [
    "CLIMATE_POLE_BLEND",
    "CLIMATE_POLE_LOCATION_TYPE",
    "ClimatePoleBlendDefaults",
    "ClimatePoleMode",
    "ClimatePolePreset",
    "ClimatePoleSpec",
    "ClimateZone",
    "ClimateZoneEntry",
    "ClimateZoneProfile",
    "ClimateZoneProfileData",
    "LOCAL_INFLUENCE_BLEND_OUTER",
    "POLE_TEMPERATURE_INSET_FRACTION",
    "PoleKind",
    "PoleSource",
    "SeasonTempOffsets",
    "WeatherTypeEntry",
    "WorldClimateScalars",
    "DEFAULT_CLIMATE_POLE_MODE",
    "DEFAULT_CLIMATE_POLE_PRESET",
    "derived_pole_temperature",
    "local_influence_fraction",
    "pole_specs_for_preset",
    "WorldClimateZoneRegistry",
    "WorldWeatherTypeRegistry",
]
