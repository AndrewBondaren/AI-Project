"""Climate builtin profiles — re-export from dataModel; resolve helpers stay here until resolve layer move."""

from app.dataModel.climate.climateZone.climateZoneEntry import ClimateZoneEntry
from app.dataModel.climate.enums.climateZone import (
    ClimateZone,
    ClimateZoneProfile,
    ClimateZoneProfileData,
)
from app.dataModel.climate.worldClimateScalars import DEFAULT_CLIMATE_ZONE


def _profile_from_entry(entry: ClimateZoneEntry, *, fallback: ClimateZoneProfile) -> ClimateZoneProfile:
    return ClimateZoneProfile(
        system_climate=entry.system_climate,
        base_temperature=entry.base_temperature if entry.base_temperature is not None else fallback.base_temperature,
        typical_elevation_z=(
            entry.typical_elevation_z if entry.typical_elevation_z is not None else fallback.typical_elevation_z
        ),
        base_rainfall=entry.base_rainfall if entry.base_rainfall is not None else fallback.base_rainfall,
        temperature_variance=(
            entry.temperature_variance if entry.temperature_variance is not None else fallback.temperature_variance
        ),
        rainfall_variance=(
            entry.rainfall_variance if entry.rainfall_variance is not None else fallback.rainfall_variance
        ),
    )


def enum_default_profile(system_climate: str) -> ClimateZoneProfile | None:
    zone = ClimateZone.from_system_climate(system_climate)
    if zone is None or zone not in ClimateZone.engine_members():
        return None
    return zone.to_profile()


def fallback_profile() -> ClimateZoneProfile:
    zone = ClimateZone.from_system_climate(DEFAULT_CLIMATE_ZONE)
    assert zone is not None
    return zone.to_profile()


__all__ = [
    "ClimateZone",
    "ClimateZoneProfile",
    "ClimateZoneProfileData",
    "_profile_from_entry",
    "enum_default_profile",
    "fallback_profile",
]
