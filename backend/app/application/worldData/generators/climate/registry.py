from app.application.worldData.generators.climate.climateZone import (
    ClimateZoneProfile,
    enum_default_profile,
    fallback_profile,
)
from app.db.models.world import World


def _registry_entries(world: World) -> list[dict]:
    raw = world.climate_zone_registry
    if not raw:
        return []
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    if isinstance(raw, dict):
        values = list(raw.values())
        if values and all(isinstance(v, dict) for v in values):
            return values
        return [raw]
    return []


def _int(entry: dict, key: str, default: int) -> int:
    value = entry.get(key)
    if value is None:
        return default
    return int(value)


def _entry_to_profile(entry: dict, fallback: ClimateZoneProfile) -> ClimateZoneProfile:
    system = entry.get("system_climate") or fallback.system_climate
    return ClimateZoneProfile(
        system_climate=system,
        base_temperature=_int(entry, "base_temperature", fallback.base_temperature),
        typical_elevation_z=_int(entry, "typical_elevation_z", fallback.typical_elevation_z),
        base_rainfall=_int(entry, "base_rainfall", fallback.base_rainfall),
        temperature_variance=_int(entry, "temperature_variance", fallback.temperature_variance),
        rainfall_variance=_int(entry, "rainfall_variance", fallback.rainfall_variance),
    )


def profile_for(world: World, system_climate: str) -> ClimateZoneProfile:
    """
    Resolve climate profile: world registry entry overrides enum defaults.
    Unknown keys fall back to TEMPERATE enum profile.
    """
    enum_default = enum_default_profile(system_climate)
    base = enum_default or fallback_profile()

    for entry in _registry_entries(world):
        key = entry.get("system_climate")
        if key == system_climate:
            return _entry_to_profile(entry, base)

    return base
