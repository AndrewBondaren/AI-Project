from app.application.worldData.generators.climate.climateZone import (
    ClimateZoneProfile,
    enum_default_profile,
    fallback_profile,
)
from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.jsonValidation import climate_zones
from app.db.models.world import World


def _int_or(value: int | None, default: int) -> int:
    return default if value is None else int(value)


def _entry_to_profile(entry, fallback: ClimateZoneProfile) -> ClimateZoneProfile:
    return ClimateZoneProfile(
        system_climate=entry.system_climate,
        base_temperature=_int_or(entry.base_temperature, fallback.base_temperature),
        typical_elevation_z=_int_or(entry.typical_elevation_z, fallback.typical_elevation_z),
        base_rainfall=_int_or(entry.base_rainfall, fallback.base_rainfall),
        temperature_variance=_int_or(entry.temperature_variance, fallback.temperature_variance),
        rainfall_variance=_int_or(entry.rainfall_variance, fallback.rainfall_variance),
    )


def profile_for(world: World, system_climate: str) -> ClimateZoneProfile:
    """
    Resolve climate profile: world registry entry overrides enum defaults.
    Unknown keys fall back to TEMPERATE enum profile.
    """
    enum_default = enum_default_profile(system_climate)
    base = enum_default or fallback_profile()

    entry = climate_zones(world).entry_for(system_climate)
    if entry is not None:
        return _entry_to_profile(entry, base)

    if enum_default is None:
        warn_once(
            world.world_uid,
            f"unknown_climate:{system_climate}",
            "climate_zone profile | world=%s unknown system_climate=%s; using temperate defaults",
            system_climate,
        )

    return base
