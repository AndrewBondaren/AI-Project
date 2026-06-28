from dataclasses import dataclass
from enum import StrEnum


class ClimateZone(StrEnum):
    """Built-in climate zone keys. Custom zones may exist only in world.climate_zone_registry."""

    ARCTIC          = "arctic"
    TUNDRA          = "tundra"
    SUBARCTIC       = "subarctic"
    SUBPOLAR        = "subpolar"
    COLD            = "cold"
    COLD_TEMPERATE  = "cold_temperate"
    TEMPERATE       = "temperate"
    CONTINENTAL     = "continental"
    ARID            = "arid"
    MEDITERRANEAN   = "mediterranean"
    SUBTROPICAL     = "subtropical"
    COASTAL         = "coastal"
    MARITIME        = "maritime"
    TROPICAL        = "tropical"
    DESERT          = "desert"
    VOLCANIC        = "volcanic"


@dataclass(frozen=True)
class ClimateZoneProfile:
    system_climate:         str
    base_temperature:       int
    typical_elevation_z:    int
    base_rainfall:          int
    temperature_variance:   int
    rainfall_variance:      int


CLIMATE_ZONE_DEFAULTS: dict[ClimateZone, ClimateZoneProfile] = {
    ClimateZone.ARCTIC: ClimateZoneProfile(
        "arctic", -25, 4, 20, 8, 10,
    ),
    ClimateZone.TUNDRA: ClimateZoneProfile(
        "tundra", -20, 3, 30, 10, 15,
    ),
    ClimateZone.SUBARCTIC: ClimateZoneProfile(
        "subarctic", -15, 3, 25, 10, 12,
    ),
    ClimateZone.SUBPOLAR: ClimateZoneProfile(
        "subpolar", -10, 2, 35, 10, 15,
    ),
    ClimateZone.COLD: ClimateZoneProfile(
        "cold", -5, 2, 40, 8, 15,
    ),
    ClimateZone.COLD_TEMPERATE: ClimateZoneProfile(
        "cold_temperate", 0, 1, 45, 8, 18,
    ),
    ClimateZone.TEMPERATE: ClimateZoneProfile(
        "temperate", 12, 0, 55, 8, 20,
    ),
    ClimateZone.CONTINENTAL: ClimateZoneProfile(
        "continental", 8, 0, 45, 10, 18,
    ),
    ClimateZone.ARID: ClimateZoneProfile(
        "arid", 20, 0, 10, 12, 5,
    ),
    ClimateZone.MEDITERRANEAN: ClimateZoneProfile(
        "mediterranean", 15, 0, 40, 8, 15,
    ),
    ClimateZone.SUBTROPICAL: ClimateZoneProfile(
        "subtropical", 22, -1, 65, 5, 15,
    ),
    ClimateZone.COASTAL: ClimateZoneProfile(
        "coastal", 14, -1, 60, 6, 18,
    ),
    ClimateZone.MARITIME: ClimateZoneProfile(
        "maritime", 12, -1, 70, 5, 20,
    ),
    ClimateZone.TROPICAL: ClimateZoneProfile(
        "tropical", 28, -1, 80, 5, 15,
    ),
    ClimateZone.DESERT: ClimateZoneProfile(
        "desert", 30, 0, 10, 12, 5,
    ),
    ClimateZone.VOLCANIC: ClimateZoneProfile(
        "volcanic", 35, 2, 5, 10, 3,
    ),
}


def enum_default_profile(system_climate: str) -> ClimateZoneProfile | None:
    try:
        zone = ClimateZone(system_climate)
    except ValueError:
        return None
    return CLIMATE_ZONE_DEFAULTS[zone]


def fallback_profile() -> ClimateZoneProfile:
    return CLIMATE_ZONE_DEFAULTS[ClimateZone.TEMPERATE]
