from dataclasses import dataclass
from typing import Optional

from app.application.worldData.generators.climate.anchorCollect import build_coarse_field
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.climateZone import ClimateZone
from app.application.worldData.generators.climate.precipitation import (
    clamp_temperature_to_peak,
    effective_rainfall,
)
from app.application.worldData.generators.climate.registry import profile_for
from app.application.worldData.generators.climate.zoneField import (
    ZoneClimateField,
    build_zone_field,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

DEFAULT_LAPSE_RATE = 0.65


@dataclass(frozen=True)
class SurfaceClimateSample:
    system_climate_zone:       str
    zone_location_uid:         str | None
    typical_elevation_z:     int
    base_temperature_override: int | None = None


class ClimateGeneratorService:
    """
    Pure utility — spatial climate assignment and per-cell weather params.
    No repositories, no async. Independent from terrain shape generation.
    """

    def build_zone_field(
        self,
        world: World,
        locations: list[NamedLocation],
        cell_m: int,
    ) -> ZoneClimateField:
        """Legacy admin-zone Voronoi (v1). Prefer pole field / anchor passes."""
        return build_zone_field(world, locations, cell_m)

    def build_coarse_field(
        self,
        world: World,
        locations: list[NamedLocation],
        cell_m: int,
    ) -> ClimateAnchorField:
        return build_coarse_field(world, locations, cell_m)

    def resolve_climate(
        self,
        world: World,
        uid_map: dict[str, NamedLocation],
        location: NamedLocation,
    ) -> str:
        current: Optional[NamedLocation] = location
        while current:
            if current.system_climate_zone:
                return current.system_climate_zone
            current = uid_map.get(current.parent_location_uid)
        return world.default_climate_zone or ClimateZone.TEMPERATE

    def sample_at_pole_field(
        self,
        world: World,
        field: ClimatePoleField,
        gx: int,
        gy: int,
    ) -> SurfaceClimateSample:
        pole = field.sample(world, gx, gy)
        return SurfaceClimateSample(
            system_climate_zone=pole.system_climate_zone,
            zone_location_uid=pole.zone_location_uid,
            typical_elevation_z=pole.typical_elevation_z,
            base_temperature_override=pole.base_temperature_override,
        )

    def sample_at_anchor_field(
        self,
        world: World,
        uid_map: dict[str, NamedLocation],
        field: ClimateAnchorField,
        gx: int,
        gy: int,
    ) -> SurfaceClimateSample:
        nearest = field.nearest(gx, gy)
        if nearest is None:
            climate = world.default_climate_zone or ClimateZone.TEMPERATE
            profile = profile_for(world, climate)
            return SurfaceClimateSample(
                system_climate_zone=profile.system_climate,
                zone_location_uid=None,
                typical_elevation_z=profile.typical_elevation_z,
            )
        profile = profile_for(world, nearest.system_climate_zone)
        return SurfaceClimateSample(
            system_climate_zone=profile.system_climate,
            zone_location_uid=nearest.location_uid,
            typical_elevation_z=profile.typical_elevation_z,
        )

    def resolve_surface_sample(
        self,
        world: World,
        uid_map: dict[str, NamedLocation],
        pole_field: ClimatePoleField,
        local_field: ClimateAnchorField,
        gx: int,
        gy: int,
    ) -> SurfaceClimateSample:
        from app.application.worldData.generators.climate.tierResolve import resolve_tier_sample

        return resolve_tier_sample(
            self, world, pole_field, local_field, gx, gy,
        )

    def sample_at_grid(
        self,
        world: World,
        uid_map: dict[str, NamedLocation],
        field: ZoneClimateField,
        gx: int,
        gy: int,
    ) -> SurfaceClimateSample:
        nearest = field.nearest_zone(gx, gy)
        climate = self._zone_climate(nearest, uid_map, world)
        profile = profile_for(world, climate)
        return SurfaceClimateSample(
            system_climate_zone=profile.system_climate,
            zone_location_uid=nearest.location_uid if nearest else None,
            typical_elevation_z=profile.typical_elevation_z,
        )

    def weather_at_elevation(
        self,
        world: World,
        system_climate: str,
        z: int,
        base_temperature_override: int | None = None,
    ) -> tuple[int, int]:
        profile = profile_for(world, system_climate)
        base    = (
            base_temperature_override
            if base_temperature_override is not None
            else profile.base_temperature
        )
        lapse = world.elevation_lapse_rate if world.elevation_lapse_rate is not None else DEFAULT_LAPSE_RATE
        temp  = round(base - lapse * (z / 100))
        temp  = clamp_temperature_to_peak(world, temp)
        rain  = effective_rainfall(profile.base_rainfall, temp, world)
        return temp, rain

    def _zone_climate(
        self,
        zone: NamedLocation | None,
        uid_map: dict[str, NamedLocation],
        world: World,
    ) -> str:
        if zone is None:
            return world.default_climate_zone or ClimateZone.TEMPERATE
        if zone.system_climate_zone:
            return zone.system_climate_zone
        return self.resolve_climate(world, uid_map, zone)
