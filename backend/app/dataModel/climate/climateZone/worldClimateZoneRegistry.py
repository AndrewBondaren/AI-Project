"""Root POJO for `worlds.climate_zone_registry`."""

from __future__ import annotations

from pydantic import RootModel

from app.dataModel.climate.climateZone.climateZoneEntry import ClimateZoneEntry

_CANONICAL_ENTRIES: tuple[ClimateZoneEntry, ...] = (
    ClimateZoneEntry(
        system_climate="arctic",
        base_temperature=-25,
        typical_elevation_z=4,
        base_rainfall=20,
        temperature_variance=8,
        rainfall_variance=10,
    ),
    ClimateZoneEntry(
        system_climate="cold",
        base_temperature=-5,
        typical_elevation_z=8,
        base_rainfall=35,
        temperature_variance=10,
        rainfall_variance=12,
    ),
    ClimateZoneEntry(
        system_climate="temperate",
        base_temperature=12,
        typical_elevation_z=12,
        base_rainfall=50,
        temperature_variance=12,
        rainfall_variance=15,
    ),
    ClimateZoneEntry(
        system_climate="warm",
        base_temperature=22,
        typical_elevation_z=10,
        base_rainfall=45,
        temperature_variance=10,
        rainfall_variance=12,
    ),
    ClimateZoneEntry(
        system_climate="tropical",
        base_temperature=28,
        typical_elevation_z=6,
        base_rainfall=80,
        temperature_variance=6,
        rainfall_variance=20,
    ),
    ClimateZoneEntry(
        system_climate="desert",
        base_temperature=32,
        typical_elevation_z=14,
        base_rainfall=8,
        temperature_variance=14,
        rainfall_variance=5,
    ),
)

# generators/climate/climateZone.py — CLIMATE_ZONE_DEFAULTS (duplicate to avoid layer import)
_ENGINE_ENTRIES: tuple[ClimateZoneEntry, ...] = (
    ClimateZoneEntry(system_climate="arctic", base_temperature=-25, typical_elevation_z=4, base_rainfall=20, temperature_variance=8, rainfall_variance=10),
    ClimateZoneEntry(system_climate="tundra", base_temperature=-20, typical_elevation_z=3, base_rainfall=30, temperature_variance=10, rainfall_variance=15),
    ClimateZoneEntry(system_climate="subarctic", base_temperature=-15, typical_elevation_z=3, base_rainfall=25, temperature_variance=10, rainfall_variance=12),
    ClimateZoneEntry(system_climate="subpolar", base_temperature=-10, typical_elevation_z=2, base_rainfall=35, temperature_variance=10, rainfall_variance=15),
    ClimateZoneEntry(system_climate="cold", base_temperature=-5, typical_elevation_z=2, base_rainfall=40, temperature_variance=8, rainfall_variance=15),
    ClimateZoneEntry(system_climate="cold_temperate", base_temperature=0, typical_elevation_z=1, base_rainfall=45, temperature_variance=8, rainfall_variance=18),
    ClimateZoneEntry(system_climate="temperate", base_temperature=12, typical_elevation_z=0, base_rainfall=55, temperature_variance=8, rainfall_variance=20),
    ClimateZoneEntry(system_climate="continental", base_temperature=8, typical_elevation_z=0, base_rainfall=45, temperature_variance=10, rainfall_variance=18),
    ClimateZoneEntry(system_climate="arid", base_temperature=20, typical_elevation_z=0, base_rainfall=10, temperature_variance=12, rainfall_variance=5),
    ClimateZoneEntry(system_climate="mediterranean", base_temperature=15, typical_elevation_z=0, base_rainfall=40, temperature_variance=8, rainfall_variance=15),
    ClimateZoneEntry(system_climate="subtropical", base_temperature=22, typical_elevation_z=-1, base_rainfall=65, temperature_variance=5, rainfall_variance=15),
    ClimateZoneEntry(system_climate="coastal", base_temperature=14, typical_elevation_z=-1, base_rainfall=60, temperature_variance=6, rainfall_variance=18),
    ClimateZoneEntry(system_climate="maritime", base_temperature=12, typical_elevation_z=-1, base_rainfall=70, temperature_variance=5, rainfall_variance=20),
    ClimateZoneEntry(system_climate="tropical", base_temperature=28, typical_elevation_z=-1, base_rainfall=80, temperature_variance=5, rainfall_variance=15),
    ClimateZoneEntry(system_climate="desert", base_temperature=30, typical_elevation_z=0, base_rainfall=10, temperature_variance=12, rainfall_variance=5),
    ClimateZoneEntry(system_climate="volcanic", base_temperature=35, typical_elevation_z=2, base_rainfall=5, temperature_variance=10, rainfall_variance=3),
)


class WorldClimateZoneRegistry(RootModel[list[ClimateZoneEntry]]):
    """Root POJO for `worlds.climate_zone_registry`. Wire shape: JSON array."""

    root: list[ClimateZoneEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldClimateZoneRegistry:
        """fixtures/world_template.json."""
        return cls(list(_CANONICAL_ENTRIES))

    @classmethod
    def canonical_engine(cls) -> WorldClimateZoneRegistry:
        """Built-in enum profiles — generators/climate/climateZone.py CLIMATE_ZONE_DEFAULTS."""
        return cls(list(_ENGINE_ENTRIES))

    def entry_for(self, system_climate: str) -> ClimateZoneEntry | None:
        for entry in self.root:
            if entry.system_climate == system_climate:
                return entry
        return None
